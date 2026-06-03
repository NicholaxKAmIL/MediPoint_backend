"""
真实舆情 API — union 查询 db.alerts (GovNotice) + db.raw_articles (微博/小红书/PTT/...)
- 数据源:
    GovNotice       <- db.alerts (FJ_WJW, FJ_CDC, NMPA, CN_CDC 爬虫写入)
    Weibo/Xiaohongshu/PTT/Dcard/GoogleNews <- db.raw_articles
- 同时返回 keyword_trend (7 日) + seven_day_series (按来源分桶)
- 每条带 entities (轻量本地查表抽取)
"""
from __future__ import annotations
import logging
import re
import sys
import pathlib
from datetime import datetime

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from fastapi import APIRouter, Query

from db.mongo import db
from services.entity_keywords import extract as extract_entities
from services.trend_analyzer import compute_keyword_trend, compute_seven_day_series

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sentiment", tags=["Sentiment"])

VALID_SOURCES = {"Weibo", "Xiaohongshu", "GovNotice", "PTT", "Dcard", "GoogleNews"}


def _basic_tags(title: str) -> list[str]:
    tags: list[str] = []
    if "感冒" in title or "流感" in title: tags.append("流感")
    if "缺" in title: tags.append("缺货")
    if "药" in title: tags.append("用药咨询")
    if "宝宝" in title or "小孩" in title: tags.append("儿童")
    if "召回" in title: tags.append("召回")
    if "新药" in title or "获批" in title: tags.append("新药")
    return tags


def _display_ts(published_at, crawled_at):
    """政府公告用原始发布时间; 没有 published_at 时回落到爬取时间。
    返回 ISO 字符串便于前后端统一序列化与排序。"""
    ts = published_at or crawled_at
    if ts is None:
        return None
    return ts.isoformat() if hasattr(ts, "isoformat") else str(ts)


def _alerts_to_items(query: dict, limit: int) -> list[dict]:
    items: list[dict] = []
    # 政府公告按"原始发布时间"排序, crawled_at 作为次级 tiebreaker
    for a in db.alerts.find(query).sort([("published_at", -1), ("crawled_at", -1)]).limit(limit):
        title = a.get("title", "")
        summary = a.get("summary", "") or ""
        text = f"{title} {summary[:120]}"
        pub = a.get("published_at")
        crawled = a.get("crawled_at")
        items.append({
            "source": "GovNotice",
            "board": a.get("source", a.get("agency", "GovNotice")),
            "title": title,
            "content": summary[:120],
            "url": a.get("url", "#"),
            "intent": "Inform",
            "tags": _basic_tags(title),
            "sentiment": a.get("sentiment", "unknown"),
            "risk_level": a.get("risk_level", "Low"),
            "agency": a.get("agency", a.get("source", "公告")),
            "published_at": pub.isoformat() if pub else None,
            "crawled_at": crawled.isoformat() if crawled else None,
            "display_at": _display_ts(pub, crawled),
            "entities": extract_entities(text),
        })
    return items


def _raw_to_items(query: dict, limit: int) -> list[dict]:
    items: list[dict] = []
    for art in db.raw_articles.find(query).sort("crawled_at", -1).limit(limit):
        title = art.get("title", "")
        content = (art.get("content", "") or "")[:120]
        text = f"{title} {content}"
        crawled = art.get("crawled_at")
        items.append({
            "source": art.get("source", "Internet"),
            "board": art.get("board", "General"),
            "title": title,
            "content": content,
            "url": art.get("url", "#"),
            "intent": art.get("intent", "Ask" if "?" in title else "Complain"),
            "tags": art.get("tags") or _basic_tags(title),
            "sentiment": art.get("sentiment", "unknown"),
            "crawled_at": crawled.isoformat() if crawled else None,
            "display_at": _display_ts(art.get("published_at"), crawled),
            "entities": extract_entities(text),
        })
    return items


@router.get("")
def list_sentiment(
    source: str = Query("all", description="Weibo | Xiaohongshu | GovNotice | PTT | Dcard | GoogleNews | all"),
    store: str = Query("S001", description="(已忽略 — 舆情数据全平台共享, 不按门店切分)"),
    limit: int = Query(50, ge=1, le=200),
):
    items: list[dict] = []
    if source == "all":
        items.extend(_alerts_to_items({}, limit))
        items.extend(_raw_to_items({}, limit))
        items.sort(key=lambda x: x.get("display_at") or "", reverse=True)
        items = items[:limit]
    elif source == "GovNotice":
        items = _alerts_to_items({}, limit)
    elif source in VALID_SOURCES:
        items = _raw_to_items({"source": source}, limit)
    else:
        items = _alerts_to_items({"source": source}, limit)
        items += _raw_to_items({"source": source}, limit)

    keyword_trend = compute_keyword_trend(days=7, top_n=7)
    seven_day_series = compute_seven_day_series(days=7)

    return {
        "items": items,
        "source_filter": source,
        "count": len(items),
        "keyword_trend": keyword_trend,
        "seven_day_series": seven_day_series,
        "fetched_at": datetime.utcnow().isoformat(),
    }
