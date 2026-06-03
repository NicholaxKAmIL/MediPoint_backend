"""
RAG 管理 API — 手动触发重索引、查询状态。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from services import rag
from util.auth import verify_credentials

router = APIRouter(prefix="/api/rag", tags=["RAG"])


@router.post("/reindex", dependencies=[Depends(verify_credentials)])
def reindex():
    """全量重建 RAG 索引。"""
    meta = rag.reindex_all()
    return meta


@router.get("/stats", dependencies=[Depends(verify_credentials)])
def stats():
    return rag.get_stats()


@router.post("/retrieve", dependencies=[Depends(verify_credentials)])
def retrieve(payload: dict):
    """调试用检索接口。"""
    q = (payload.get("query") or "").strip()
    if not q:
        return {"items": []}
    top_k = int(payload.get("top_k") or 5)
    source_types = payload.get("source_types")
    items = rag.retrieve(q, top_k=top_k, source_types=source_types)
    return {"items": items}
