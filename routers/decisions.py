"""真实补货/促销决策 API (从 Mongo 实时聚合)"""
from fastapi import APIRouter, Query

from services.decisions import get_decisions

router = APIRouter(prefix="/api/decisions", tags=["Decisions"])


@router.get("")
def list_decisions(store: str = Query("S001", description="门店 ID")):
    """根据门店 ID 返回补货 (restock) + 促销 (promotion) 建议。"""
    return get_decisions(store)
