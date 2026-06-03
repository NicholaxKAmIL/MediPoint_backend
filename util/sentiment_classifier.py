"""
LLM 情感分类器 — 串行调用 + Mongo 缓存
- 启动时一次性给最近 N 条 alerts 打标签, 不阻塞启动
- 缓存字段: db.alerts.sentiment (key = url)
- 失败时写入 "unknown", 前端按中性显示
"""
from __future__ import annotations
import logging
import sys
import pathlib
import time
from datetime import datetime, timedelta

from pymongo import UpdateOne

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from util.llm import classify_sentiment, SENTIMENT_LABELS  # noqa: E402

log = logging.getLogger(__name__)

# 限流: DeepSeek 60 RPM ≈ 1 req/s, 串行 + 间隔 1.1s 稳妥
_REQUEST_INTERVAL_S = 1.1
_last_request_ts: float = 0.0


def _throttle():
    global _last_request_ts
    wait = _REQUEST_INTERVAL_S - (time.time() - _last_request_ts)
    if wait > 0:
        time.sleep(wait)
    _last_request_ts = time.time()


def _heuristic_label(title: str, summary: str = "") -> str:
    """LLM 不可用时的兜底 — 用标题关键词做粗判, 与 LLM 4 类对齐。"""
    text = f"{title} {summary}"
    neg = ("召回", "严重", "死亡", "突发", "聚集性疫情", "一级召回", "三级召回")
    concern = ("上升", "高峰", "增加", "聚集", "预警", "风险提示", "不良反应",
               "流行", "扩散", "ILI", "手足口", "诺如")
    pos = ("获批", "上市", "免费", "接种", "利好", "便民", "新药")
    if any(k in text for k in neg):
        return "negative"
    if any(k in text for k in concern):
        return "concern"
    if any(k in text for k in pos):
        return "positive"
    return "neutral"


def classify_one(url: str, title: str, summary: str = "", force: bool = False) -> str:
    """对单条 alert 做分类; 已分类且 force=False 时直接返回缓存值。"""
    if not force:
        existing = db.alerts.find_one({"url": url}, {"sentiment": 1})
        if existing and existing.get("sentiment"):
            return existing["sentiment"]

    label = classify_sentiment(title, summary)
    if label is None:
        label = _heuristic_label(title, summary)
        if label is None:
            label = "unknown"

    try:
        db.alerts.update_one({"url": url}, {"$set": {"sentiment": label}})
    except Exception as e:
        log.warning("sentiment cache write failed: %s", e)
    return label


def classify_pending_alerts(batch_size: int = 30, since_days: int = 60) -> dict:
    """对最近 since_days 天内尚未分类的 alert 逐条打标签, 返回统计。
    串行 + 限流, 不会阻塞启动 (作为后台线程跑)。
    """
    since = datetime.utcnow() - timedelta(days=since_days)
    pending = list(
        db.alerts.find(
            {"crawled_at": {"$gte": since}, "sentiment": {"$exists": False}},
        )
        .sort("crawled_at", -1)
        .limit(batch_size)
    )
    if not pending:
        return {"scanned": 0, "classified": 0, "errors": 0}

    classified = 0
    errors = 0
    for a in pending:
        url = a.get("url")
        if not url:
            continue
        try:
            classify_one(url, a.get("title", ""), a.get("summary", ""), force=True)
            classified += 1
        except Exception as e:
            log.warning("classify_pending_alerts item failed: %s", e)
            errors += 1
        _throttle()

    return {"scanned": len(pending), "classified": classified, "errors": errors}
