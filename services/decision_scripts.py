"""
Decision 脚本缓存 — 把 LLM 生成的 talking_points / reason 存到 Mongo,
供前端按需异步拉取, 不再阻塞主 API 返回。
- 公开 key: store_id + date + action + related_category (前端构造)
- 实际缓存 key: 在公开 key 基础上拼接 content_hash (SKU+库存快照),
  库存一旦变化, 自动失效, 触发 LLM 重新生成
- TTL 12 小时, 但 content_hash 变化时立即失效
- 调用: get_cached(public_key, content_key) / get_or_generate(..., content_key)
"""
from __future__ import annotations
import hashlib
import logging
import sys
import pathlib
from datetime import datetime

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from util.llm import generate_reason, generate_marketing_pair  # noqa: E402

log = logging.getLogger(__name__)

COLL = "decision_scripts"

# 同 store+date+action+category+content_hash 的脚本 12 小时内复用
REFRESH_AFTER_HOURS = 12

# 单品时的品类关联推荐表 — 与 talking_points 中提到的产品方向严格一致
_CATEGORY_UPSELL: list[tuple[list[str], str]] = [
    (["感冒", "流感", "呼吸道", "连花清瘟", "感冒灵", "氨酚烷胺"], "建议搭配：复方氨酚烷胺片 + 抗病毒口服液"),
    (["退烧", "布洛芬", "对乙酰", "美林", "泰诺"], "建议搭配：对乙酰氨基酚 + 电子体温计"),
    (["清热", "板蓝根", "蒲地蓝", "鱼腥草", "二丁", "抗病毒"], "建议搭配：蒲地蓝消炎口服液 + 抗病毒口服液"),
    (["中成药", "中成"], "建议搭配：同类中成药 + 西药辅助"),
    (["肠胃", "胃", "腹泻", "腹胀", "消化", "藿香", "保和"], "建议搭配：益生菌 + 口服补液盐"),
    (["过敏", "鼻喷", "鼻炎", "花粉", "莫米松", "氯雷他定"], "建议搭配：糠酸莫米松鼻喷雾 + 生理盐水鼻喷"),
    (["咳嗽", "止咳", "急支糖浆", "右美沙芬", "甘草"], "建议搭配：复方甘草片 + 急支糖浆"),
    (["维生素", "维C", "泡腾", "钙", "钙尔奇"], "建议搭配：复合维生素 + 钙尔奇 D"),
    (["蛋白", "乳清"], "建议搭配：蛋白粉 + 维生素"),
    (["咽喉", "含片", "草珊瑚", "西瓜霜"], "建议搭配：复方草珊瑚含片 + 胖大海"),
    (["儿科", "小儿", "儿童", "宝宝", "氨酚黄那敏"], "建议搭配：小儿氨酚黄那敏 + 儿童退热贴"),
    (["外用", "创可贴", "邦迪"], "建议搭配：碘伏消毒液 + 创可贴"),
    (["安神", "助眠", "眠安宁"], "建议搭配：酸枣仁 + 助眠茶"),
    (["降糖", "SGLT2", "恒格列净"], "建议搭配：二甲双胍 + 血糖仪试纸"),
    (["疫苗"], "建议搭配：流感疫苗预约 + 体温计"),
]


def _static_upsell(sku_names: list[str], category: str) -> str:
    """根据 category 关键词查表 — 与 LLM 提到的产品方向严格一致。
    - 2+ SKU: 块内互搭 (cross-sell, 一定是品类内产品)
    - 1 SKU: 静态表推荐同方向产品 (避免推荐维生素C等无关商品)
    """
    if len(sku_names) >= 2:
        return f"建议搭配：{sku_names[0]} + {sku_names[1]}"
    keywords = [category] + sku_names
    for kws, upsell in _CATEGORY_UPSELL:
        if any(any(kw in s for kw in kws) for s in keywords):
            return upsell
    return "建议搭配：店内同类热销品"


def make_key(store_id: str, date: str, action: str, category: str) -> str:
    """公开 key — 前端用。"""
    return f"{store_id}|{date}|{action}|{category}"


def compute_content_key(sku_rows: list[dict]) -> str:
    """根据 (sku_id + closing_on_hand + margin) 列表算 content hash。
    库存一旦变化, hash 立即变化, 缓存自动失效。
    """
    sig_parts = sorted(
        (r.get("sku_id", ""), int(r.get("closing_on_hand", 0)), float(r.get("margin", 0)))
        for r in sku_rows
    )
    raw = "|".join(f"{sid}:{stk}:{mrg}" for sid, stk, mrg in sig_parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def _is_fresh(doc: dict) -> bool:
    ts = doc.get("generated_at")
    if not ts:
        return False
    age = datetime.utcnow() - ts
    return age.total_seconds() < REFRESH_AFTER_HOURS * 3600


def get_cached(public_key: str, content_key: str) -> dict | None:
    return db[COLL].find_one({"_key": f"{public_key}|{content_key}"})


def get_or_generate(
    store_id: str,
    date: str,
    action: str,
    category: str,
    sku_names: list[str],
    alert_titles: list[str],
    min_stock: int,
    content_key: str = "",
) -> dict:
    """返回 {talking_points, reason, generated_at, from_cache}。
    缓存命中直接返回, 否则调 LLM 写库。
    `content_key` 由调用方基于库存快照算出 — 库存变了就自动失效。
    """
    public_key = make_key(store_id, date, action, category)
    cache_key = f"{public_key}|{content_key}" if content_key else public_key

    cached = get_cached(public_key, content_key) if content_key else db[COLL].find_one({"_key": cache_key})
    if cached and _is_fresh(cached):
        return {
            "talking_points": cached.get("talking_points", ""),
            "upsell": cached.get("upsell", ""),
            "reason": cached.get("reason", ""),
            "generated_at": cached.get("generated_at").isoformat() if cached.get("generated_at") else None,
            "from_cache": True,
        }

    if action == "Restock":
        reason = generate_reason(category, sku_names, min_stock, alert_titles)
        topic = f"{category} 库存偏低, 顾客询问较多"
    else:
        if alert_titles:
            reason = (
                f"店内 {category} 库存偏高 ({min_stock} 盒), 建议组合促销去化; "
                f"近期相关: {alert_titles[0][:30]}"
            )
        else:
            reason = f"店内 {category} 库存偏高 ({min_stock} 盒), 建议组合促销去化。"
        topic = f"{category} 库存偏高, 需要主动行销去化"

    pair = generate_marketing_pair(topic, sku_names, reason)
    talk = pair["talking_point"]
    # 搭配推荐用静态表, 保证与 LLM 话术中提到的产品方向一致 (避免 LLM 随意推荐维生素C等)
    upsell = _static_upsell(sku_names, category)

    doc = {
        "_key": cache_key,
        "store_id": store_id,
        "date": date,
        "action": action,
        "category": category,
        "content_key": content_key,
        "talking_points": talk,
        "upsell": upsell,
        "reason": reason,
        "generated_at": datetime.utcnow(),
    }
    try:
        db[COLL].update_one({"_key": cache_key}, {"$set": doc}, upsert=True)
    except Exception as e:
        log.warning("decision_scripts write failed: %s", e)
    return {
        "talking_points": talk,
        "upsell": upsell,
        "reason": reason,
        "generated_at": doc["generated_at"].isoformat(),
        "from_cache": False,
    }
