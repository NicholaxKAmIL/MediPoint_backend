import logging
import os
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

from db.mongo import db
from routers import chat, crawler, dashboard, decisions, decisions_scripts, mock, rag_router, regulations, sentiment
from services.crawler_status import get_status as get_crawler_status
from services.crawlers import run_all_crawlers
from services import seed_kb, rag as rag_service
from util.auth import verify_credentials
from util.config import Env
from util.sentiment_classifier import classify_pending_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("medipoint")

# 启动时是否自动跑爬虫 (生产可设为 false, 用 /api/crawler/run 手动触发)
RUN_CRAWLER_ON_STARTUP = os.getenv("RUN_CRAWLER_ON_STARTUP", "true").lower() == "true"
# 多久内 (小时) 已抓过则跳过启动爬虫
STARTUP_CRAWL_MIN_INTERVAL_HOURS = float(os.getenv("STARTUP_CRAWL_MIN_INTERVAL_HOURS", "6"))

# 启动后台线程 — 每个 worker 独立的 Event, 避免互相短电路 shutdown 等待
_crawl_thread: threading.Thread | None = None
_crawl_done = threading.Event()
_index_thread: threading.Thread | None = None
_index_done = threading.Event()
_sentiment_thread: threading.Thread | None = None
_sentiment_done = threading.Event()


def _index_worker():
    try:
        seed_kb.seed_if_empty()
        meta = rag_service.reindex_all()
        log.info("RAG 索引完成: %s", meta)
    except Exception:
        log.exception("RAG 启动索引失败")
    finally:
        _index_done.set()


def _sentiment_worker():
    try:
        result = classify_pending_alerts(batch_size=30, since_days=60)
        log.info("启动 sentiment 分类完成: %s", result)
    except Exception:
        log.exception("启动 sentiment 分类失败")
    finally:
        _sentiment_done.set()


def _should_run_startup_crawl() -> bool:
    if not RUN_CRAWLER_ON_STARTUP:
        return False
    last = get_crawler_status().get("last_run")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last)
    except ValueError:
        return True
    return datetime.utcnow() - last_dt > timedelta(hours=STARTUP_CRAWL_MIN_INTERVAL_HOURS)


def _crawl_worker():
    try:
        results = run_all_crawlers()
        log.info("初次爬虫完成: %s", results)
    except Exception:
        log.exception("初次爬虫失败")
    finally:
        _crawl_done.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _crawl_thread, _index_thread, _sentiment_thread
    log.info("MediPoint API 启动 — 灌静态 KB + 建 RAG 索引 (后台)…")
    _crawl_done.clear()
    _index_done.clear()
    _sentiment_done.clear()
    _index_thread = threading.Thread(target=_index_worker, daemon=True)
    _index_thread.start()

    if _should_run_startup_crawl():
        log.info("MediPoint API 启动 — 后台执行初次爬虫…")
        _crawl_thread = threading.Thread(target=_crawl_worker, daemon=True)
        _crawl_thread.start()
    else:
        log.info("MediPoint API 启动 — 跳过初次爬虫 (距上次抓取 < %sh)", STARTUP_CRAWL_MIN_INTERVAL_HOURS)

    log.info("MediPoint API 启动 — 后台批量分类 alerts sentiment…")
    _sentiment_thread = threading.Thread(target=_sentiment_worker, daemon=True)
    _sentiment_thread.start()

    yield
    if _crawl_thread and _crawl_thread.is_alive():
        _crawl_done.wait(timeout=30)
    if _index_thread and _index_thread.is_alive():
        _index_done.wait(timeout=30)
    if _sentiment_thread and _sentiment_thread.is_alive():
        _sentiment_done.wait(timeout=60)


app = FastAPI(
    title="MediPoint API",
    description="[MediPoint] - ERP 智慧商情系統 API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_openapi(title="MediPoint API", version="1.0.0", routes=app.routes)


@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="MediPoint API")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_redoc_html(openapi_url="/openapi.json", title="MediPoint API")


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "https://uie47061.github.io",
]
_extra_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
if _extra_origin:
    origins.append(_extra_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "Welcome to MediPoint API!", "status": "running"}


@app.get("/health")
def health_check():
    """健康检查: Mongo + LLM key + 爬虫状态。"""
    mongo_ok = False
    try:
        db.command("ping")
        mongo_ok = True
    except Exception as e:
        log.warning("mongo ping failed: %s", e)

    crawler = get_crawler_status()
    return {
        "status": "ok" if mongo_ok else "degraded",
        "mongo": "ok" if mongo_ok else "error",
        "llm_configured": bool(Env.DEEPSEEK_API_KEY),
        "crawler_last_run": crawler.get("last_run"),
        "crawler_results": crawler.get("results"),
        "ts": datetime.now(timezone.utc).isoformat(),
    }


# 所有数据 API 统一加 HTTPBasic 保护 (与 /docs 一致)
_DATA_AUTH = [Depends(verify_credentials)]
app.include_router(dashboard.router, dependencies=_DATA_AUTH)
app.include_router(decisions.router, dependencies=_DATA_AUTH)
app.include_router(decisions_scripts.router, dependencies=_DATA_AUTH)
app.include_router(sentiment.router, dependencies=_DATA_AUTH)
app.include_router(regulations.router, dependencies=_DATA_AUTH)
app.include_router(crawler.router, dependencies=_DATA_AUTH)
app.include_router(chat.router, dependencies=_DATA_AUTH)
app.include_router(rag_router.router, dependencies=_DATA_AUTH)
if Env.ENABLE_MOCK:
    app.include_router(mock.router, dependencies=_DATA_AUTH)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=Env.PORT, reload=Env.RELOAD)
