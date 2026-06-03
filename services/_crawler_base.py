"""
通用抓取器: live fetch -> static cache fallback
供 FJ CDC / NMPA 等站点共享, 避免 triplicated _persist / _try_live_fetch
"""
from __future__ import annotations
import logging
import sys
import pathlib
from datetime import datetime
from typing import Callable

import requests
from bs4 import BeautifulSoup
from pymongo import UpdateOne

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
from db.mongo import db  # noqa: E402

log = logging.getLogger(__name__)


def _persist_items(items: list[dict]) -> dict:
    """分批 upsert. 返回 {new, updated}."""
    if not items:
        return {"new": 0, "updated": 0}
    urls = [it["url"] for it in items]
    existing = {d["url"] for d in db.alerts.find({"url": {"$in": urls}}, {"url": 1})}
    new_items, existing_items = [], []
    for it in items:
        (new_items if it["url"] not in existing else existing_items).append(it)

    if new_items:
        db.alerts.insert_many(new_items)
    if existing_items:
        ops = [
            UpdateOne(
                {"url": it["url"]},
                {"$set": {
                    **{k: v for k, v in it.items() if k != "_id"},
                    "crawled_at": datetime.utcnow(),
                }},
            ) for it in existing_items
        ]
        db.alerts.bulk_write(ops, ordered=False)
    return {"new": len(new_items), "updated": len(existing_items)}


def _parse_anchors(html: str, source: str, agency: str, min_title_len: int, base_url: str, limit: int) -> list[dict]:
    """通用 list 页解析: 抓 anchor 含 title 且非 javascript: 链接."""
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    for a in soup.select("a"):
        title = (a.get("title") or a.get_text() or "").strip()
        href = a.get("href", "").strip()
        if not title or not href or len(title) < min_title_len:
            continue
        if "javascript" in href.lower() or href.startswith("#"):
            continue
        items.append({
            "source": source,
            "agency": agency,
            "title": title,
            "url": href if href.startswith("http") else urljoin(base_url, href),
            "risk_level": "Medium",
            "crawled_via": "live",
            "crawled_at": datetime.utcnow(),
        })
        if len(items) >= limit:
            break
    return items


def run_with_static_fallback(
    name: str,
    live_urls: list[str],
    static_items: list[dict],
    parser: Callable[[str, str], list[dict]],
    *,
    seed_static_if_empty: bool = True,
) -> dict:
    """
    通用 live -> static fallback 流程.
    - live_urls: 顺序尝试的 URL 列表 (首个成功即用)
    - static_items: 全部失败时写入的静态数据
    - parser(html, base_url) -> list[dict]
    - seed_static_if_empty: 仅当 db.alerts 完全为空时才 seed 静态数据
                            (避免每次重启都重新插入)
    """
    for url in live_urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            r.raise_for_status()
            items = parser(r.text, url)
            if items:
                result = _persist_items(items)
                return {"count": result["new"], "updated": result["updated"], "mode": "live", "url": url}
        except Exception as e:
            log.info("[%s] live fetch %s failed: %s", name, url, e)

    # 全部失败, 走静态兜底
    if not seed_static_if_empty or db.alerts.count_documents({}) > 0:
        # 已有真实数据, 静态兜底只用于"补充缺失项"
        existing_urls = {d["url"] for d in db.alerts.find({"source": name.split("_")[0].upper() if "_" in name else name}, {"url": 1})}
        to_seed = [it for it in static_items if it["url"] not in existing_urls]
        if not to_seed:
            return {"count": 0, "updated": 0, "mode": "static_fallback_noop"}
        result = _persist_items(to_seed)
        return {"count": result["new"], "updated": result["updated"], "mode": "static_fallback_supplement"}
    # 首次部署 + alerts 全空: 写入全部静态数据
    result = _persist_items(static_items)
    return {"count": result["new"], "updated": result["updated"], "mode": "static_fallback_seed"}
