"""
共享 HTTPBasic 认证 (与 /docs 用同一套账号)
"""
import secrets
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from util.config import Env

security = HTTPBasic()
DOCS_USERNAME = Env.DOCS_USERNAME
DOCS_PASSWORD = Env.DOCS_PASSWORD


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
