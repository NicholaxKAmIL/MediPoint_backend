from fastapi import APIRouter
from pydantic import BaseModel
from services import mock_data

router = APIRouter(prefix="/api/mock", tags=["Mock"])


@router.get("/dashboard")
def mock_dashboard():
    """全量模拟 Dashboard 数据"""
    return mock_data.dashboard_payload()


@router.get("/sentiment")
def mock_sentiment():
    """全网舆情 (微博 / 小红书 / 政府公告)"""
    return mock_data.sentiment_payload()


@router.get("/decisions")
def mock_decisions():
    """AI 采购决策 (补货 + 促销)"""
    return mock_data.decisions_payload()


@router.get("/regulations")
def mock_regulations():
    """法规政策通告 (NMPA / 福建卫健委 / 福建 CDC)"""
    return mock_data.regulations_payload()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def mock_chat(req: ChatRequest):
    """AI 药师助手对话 (基于 FAQ 关键词匹配)"""
    return mock_data.chat_reply(req.message)
