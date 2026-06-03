"""
决策脚本 (talking_points + reason) 异步接口
- 主 /api/decisions 不再调 LLM, 同步返回数据, 每块带 script_key
- 前端按 script_key 调本接口拉取 (并缓存 Mongo)
- 缓存 key 在公开 (store|date|action|category) 基础上拼接 content_hash,
  库存/毛利率一旦变化, 缓存自动失效, 触发重新生成
- TTL 12 小时, 但 content_hash 变化时立即失效
"""
from fastapi import APIRouter, HTTPException, Query

from services.decision_scripts import compute_content_key, get_cached, get_or_generate

router = APIRouter(prefix="/api/decisions", tags=["Decisions"])


@router.get("/script")
def get_script(
    key: str = Query(..., description="S001|2026-06-03|Restock|感冒/退烧"),
    refresh: bool = Query(False, description="强制重新生成 (忽略缓存)"),
):
    """返回 {talking_points, reason, generated_at, from_cache}。"""
    parts = key.split("|")
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="key format: store_id|date|action|category")
    store_id, date, action, category = parts
    if action not in ("Restock", "Promotion"):
        raise HTTPException(status_code=400, detail="action must be Restock or Promotion")

    from services.decisions import _find_relevant_alerts
    from services.sku_category_map import normalize_category
    from db.mongo import db

    all_rows = list(db.inventory.find({
        "store_id": store_id,
        "date": date,
    }).sort("closing_on_hand", 1 if action == "Restock" else -1).limit(50))

    # 关键修复: 只统计当前 category 的 SKU, 避免用别品的库存数串到当前品类
    category_rows = [
        r for r in all_rows
        if (r.get("category") or normalize_category(r.get("sku_name", ""))) == category
    ]
    if not category_rows:
        category_rows = all_rows[:5]

    content_key = compute_content_key(all_rows)

    target_names = [r.get("sku_name", "") for r in category_rows if r.get("sku_name")]
    if not target_names:
        target_names = [r.get("sku_name", "") for r in all_rows[:3] if r.get("sku_name")]

    min_stock = min((r.get("closing_on_hand", 0) for r in category_rows), default=0)
    alerts = _find_relevant_alerts(category) if action == "Restock" else []
    alert_titles = [a["title"] for a in alerts]

    if not refresh:
        cached = get_cached(key, content_key)
        if cached:
            return {
                "key": key,
                "talking_points": cached.get("talking_points", ""),
                "reason": cached.get("reason", ""),
                "generated_at": cached.get("generated_at").isoformat() if cached.get("generated_at") else None,
                "from_cache": True,
            }

    result = get_or_generate(
        store_id=store_id,
        date=date,
        action=action,
        category=category,
        sku_names=target_names,
        alert_titles=alert_titles,
        min_stock=min_stock,
        content_key=content_key,
    )
    return {"key": key, **result}
