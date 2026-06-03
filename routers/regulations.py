"""
真实法规/公告 API — 从 db.alerts 读取
- 过滤 published_at 为 None 的项 (FJ WJW URL 日期解析失败时), 它们会在 desc 排序中排到最前
- 排序键: published_at desc + crawled_at desc (次级)
"""
from fastapi import APIRouter, Query
from datetime import datetime

from db.mongo import db

router = APIRouter(prefix="/api/regulations", tags=["Regulations"])


@router.get("")
def list_regulations(
    source: str = Query("all", description="NMPA | FJ_WJW | FJ_CDC | CN_CDC | all"),
    risk_level: str = Query("all", description="High | Medium | Low | all"),
    limit: int = Query(200, ge=1, le=500),
):
    query: dict = {}
    if source != "all":
        query["source"] = source
    if risk_level != "all":
        query["risk_level"] = risk_level

    items = []
    # 多取一些, Python 端过滤 None (desc 排序中 None 会排到最前)
    cursor = (
        db.alerts
        .find(query)
        .sort([("published_at", -1), ("crawled_at", -1)])
        .limit(limit * 2)
    )
    for a in cursor:
        pub = a.get("published_at") or a.get("crawled_at")
        if pub is None:
            continue
        items.append({
            "source": a.get("source", "Unknown"),
            "agency": a.get("agency", a.get("source_agency", a.get("source", ""))),
            "category": a.get("category", "公告"),
            "type": a.get("type", a.get("category", "公告")),
            "title": a.get("title", ""),
            "url": a.get("url", "#"),
            "summary": a.get("summary", ""),
            "affected_categories": a.get("affected_categories", []),
            "risk_level": a.get("risk_level", "Medium"),
            "published_at": pub.isoformat(),
            "crawled_at": a["crawled_at"].isoformat() if a.get("crawled_at") else None,
            "crawled_via": a.get("crawled_via", "live"),
        })
        if len(items) >= limit:
            break

    return {
        "items": items,
        "source_filter": source,
        "risk_filter": risk_level,
        "count": len(items),
        "fetched_at": datetime.utcnow().isoformat(),
    }
