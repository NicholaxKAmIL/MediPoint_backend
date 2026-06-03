"""
真实决策聚合 — 从 db.inventory + db.alerts 生成补货/促销建议
- 与 dashboard 用同一个业务日期 (Asia/Shanghai yesterday)
- 每个标准化 category 一个 block (多块输出)
- 关联 db.alerts: 优先按 affected_categories 字段, 缺失时 fallback 到 title 关键词匹配, 14 天窗
- 主接口不走 LLM: 同步返回所有非 LLM 字段, talking_points/reason 留空
  + script_key, 前端通过 /api/decisions/script 异步拉取 (并缓存)
- confidence: 高风险 alert + 库存<15 → A, 中风险 + 库存<30 → B, 仅库存 → C
"""
from __future__ import annotations
import logging
import sys
import pathlib
import re
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from services.decision_scripts import make_key  # noqa: E402
from services.sku_category_map import (  # noqa: E402
    normalize_category,
    keywords_for_category,
    STANDARD_CATEGORIES,
)

log = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
    _BUSINESS_TZ = ZoneInfo("Asia/Shanghai")
except ImportError:
    from datetime import timezone, timedelta
    _BUSINESS_TZ = timezone(timedelta(hours=8))


def _business_yesterday() -> str:
    return (datetime.now(_BUSINESS_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")


def _latest_inventory_date(store_id: str) -> str | None:
    doc = db.inventory.find_one(
        {"store_id": store_id}, sort=[("date", -1)]
    )
    return doc["date"] if doc else None


def _find_relevant_alerts(category: str, days: int = 14, limit: int = 5) -> list[dict]:
    """在 db.alerts 中找与 category 相关的公告。
    策略:
      1) affected_categories 字段包含 category 名 (or keyword hit)
      2) fallback: title 命中 keywords_for_category(category)
    按 risk_level 权重 + crawled_at 排序
    """
    since = datetime.utcnow() - timedelta(days=days)
    kws = keywords_for_category(category)
    if not kws:
        return []
    or_clauses: list[dict] = []
    or_clauses.append({"affected_categories": {"$regex": category, "$options": "i"}})
    for kw in kws:
        or_clauses.append({"title": {"$regex": re.escape(kw), "$options": "i"}})
        or_clauses.append({"summary": {"$regex": re.escape(kw), "$options": "i"}})

    cursor = db.alerts.find({
        "$or": or_clauses,
        "crawled_at": {"$gte": since},
    }).limit(limit * 4)

    risk_weight = {"High": 3, "Medium": 2, "Low": 1}
    ranked = sorted(
        cursor,
        key=lambda d: (
            risk_weight.get(d.get("risk_level", "Low"), 0),
            d.get("crawled_at") or datetime.min,
        ),
        reverse=True,
    )
    return [
        {
            "title": d.get("title", ""),
            "url": d.get("url", "#"),
            "agency": d.get("agency", d.get("source", "公告")),
            "risk_level": d.get("risk_level", "Low"),
            "published_at": d.get("published_at").isoformat() if d.get("published_at") else None,
        }
        for d in ranked[:limit]
    ]


def _compute_confidence(alerts: list[dict], min_stock: int) -> str:
    """根据最严重 alert + 最低库存 计算 confidence (A/B/C)。"""
    has_high = any(a.get("risk_level") == "High" for a in alerts)
    has_medium = any(a.get("risk_level") == "Medium" for a in alerts)
    if has_high and min_stock < 15:
        return "A"
    if (has_high or has_medium) and min_stock < 30:
        return "B"
    return "C"


def _build_block(
    store_id: str,
    date: str,
    action: str,
    category: str,
    items: list[dict],
    alerts: list[dict],
    min_stock: int,
) -> dict:
    confidence = _compute_confidence(alerts, min_stock)
    alert_titles = [a["title"] for a in alerts]

    sources: list[dict] = []
    for a in alerts:
        sources.append({
            "label": f"🔔 {a['agency']} — {a['title'][:30]}{'…' if len(a['title']) > 30 else ''}",
            "url": a["url"],
            "type": "alert",
            "agency": a["agency"],
            "risk_level": a["risk_level"],
        })
    sources.append({"label": "店内 ERP 库存", "url": "#", "type": "erp"})

    topic_action = "补货" if action == "Restock" else "促销去化"

    return {
        "id": f"{action}-{category}",
        "topic": f"{category} {topic_action}",
        "action": action,
        "related_category": category,
        "reason": "",
        "confidence": confidence,
        "sources": sources,
        "items": items,
        "talking_points": None,
        "script_key": make_key(store_id, date, action, category),
    }


def get_decisions(store_id: str = "S001") -> dict:
    store = store_id or "S001"
    target_date = _latest_inventory_date(store) or _business_yesterday()

    low = list(db.inventory.find({
        "date": target_date, "store_id": store, "closing_on_hand": {"$lt": 30},
    }).sort("closing_on_hand", 1).limit(15))
    high = list(db.inventory.find({
        "date": target_date, "store_id": store, "closing_on_hand": {"$gt": 100},
    }).sort("closing_on_hand", -1).limit(10))

    restock: list[dict] = []
    if low:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for it in low:
            sku_name = it.get("sku_name", it.get("sku_id", ""))
            cat = it.get("category") or normalize_category(sku_name)
            grouped[cat].append(it)

        for cat, items in grouped.items():
            items_sorted = sorted(items, key=lambda x: x["closing_on_hand"])[:5]
            blocks = [
                {
                    "sku_id": it["sku_id"],
                    "name": it.get("sku_name", it["sku_id"]),
                    "stock": it["closing_on_hand"],
                    "margin": it.get("margin", 30.0),
                    "sales_7d": it.get("sales_7d", 0),
                    "status": "Critical" if it["closing_on_hand"] < 15 else "Warning",
                } for it in items_sorted
            ]
            min_stock = min(b["stock"] for b in blocks)
            alerts = _find_relevant_alerts(cat)
            restock.append(_build_block(store, target_date, "Restock", cat, blocks, alerts, min_stock))

        confidence_rank = {"A": 0, "B": 1, "C": 2}
        restock.sort(key=lambda b: (confidence_rank.get(b["confidence"], 3), b["items"][0]["stock"]))

    promotion: list[dict] = []
    if high:
        grouped_h: dict[str, list[dict]] = defaultdict(list)
        for it in high:
            sku_name = it.get("sku_name", it.get("sku_id", ""))
            cat = it.get("category") or normalize_category(sku_name)
            grouped_h[cat].append(it)

        for cat, items in grouped_h.items():
            items_sorted = sorted(items, key=lambda x: -x["closing_on_hand"])[:5]
            blocks = [
                {
                    "sku_id": it["sku_id"],
                    "name": it.get("sku_name", it["sku_id"]),
                    "stock": it["closing_on_hand"],
                    "margin": it.get("margin", 35.0),
                    "sales_7d": it.get("sales_7d", 0),
                    "status": "Overstock",
                } for it in items_sorted
            ]
            min_stock = min(b["stock"] for b in blocks)
            alerts = _find_relevant_alerts(cat)
            promotion.append(_build_block(store, target_date, "Promotion", cat, blocks, alerts, min_stock))

        confidence_rank = {"A": 0, "B": 1, "C": 2}
        promotion.sort(key=lambda b: (confidence_rank.get(b["confidence"], 3), -b["items"][0]["stock"]))

    return {
        "store_id": store,
        "date": target_date,
        "restock": restock,
        "promotion": promotion,
    }
