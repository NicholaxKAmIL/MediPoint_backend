from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from util.config import Env
import secrets

# 引入 Routers
from routers import dashboard, crawler, mock

# 初始化 HTTPBasic 認證
security = HTTPBasic()

app = FastAPI(
    title="MediPoint API",
    description="[MediPoint] - ERP 智慧商情系統 API",
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# 從環境變數讀取 /docs 帳密
DOCS_USERNAME = Env.DOCS_USERNAME
DOCS_PASSWORD = Env.DOCS_PASSWORD

# 驗證函數
def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, DOCS_USERNAME)
    correct_password = secrets.compare_digest(credentials.password, DOCS_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=401,
            detail="無效的憑證",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials

# 受保護的 OpenAPI schema
@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_openapi(title="MediPoint API", version="1.0.0", routes=app.routes)

# 受保護的 Swagger UI
@app.get("/docs", include_in_schema=False)
async def get_swagger_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="MediPoint API")

# 受保護的 ReDoc
@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(credentials: HTTPBasicCredentials = Depends(verify_credentials)):
    return get_redoc_html(openapi_url="/openapi.json", title="MediPoint API")

# CORS 設定
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://uie47061.github.io",
    "https://huggingface.co",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # 允許所有來源，方便開發，正式環境建議設限
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    """根路由"""
    return {"message": "Welcome to MediPoint API!", "status": "running"}

@app.get("/health")
def health_check():
    """健康檢查"""
    return {"status": "ok"}

# 註冊路由
app.include_router(dashboard.router)
app.include_router(crawler.router)
if Env.ENABLE_MOCK:
    app.include_router(mock.router)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=Env.PORT, reload=True)
    # uvicorn app:app --port 7860 --reload