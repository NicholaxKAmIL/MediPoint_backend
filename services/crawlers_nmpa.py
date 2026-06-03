"""
NMPA 爬虫 (带静态 cache 兜底)
- 真实抓取: cloudscraper 尝试绕过 JS 反爬 (WAF 412 仍会失败, 这是已知限制)
- 失败时: 静态数据仅在 alerts 全空时 seed, 否则只补充缺失项
- 尝试的入口: 药品 / 公告通稿 (yaopin/ypggtg) — 后者含处方转换 / 说明书修订等
"""
from __future__ import annotations
import sys
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
from services._crawler_base import _parse_anchors, _persist_items, run_with_static_fallback  # noqa: E402
from services.static_cache_nmpa import STATIC_NMPA_ALERTS  # noqa: E402


def _live_fetch(url: str) -> str:
    """cloudscraper 优先, 失败回退 requests."""
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        r = scraper.get(url, timeout=8)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    import requests
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    r.raise_for_status()
    return r.text


def _parser(html: str, base_url: str) -> list[dict]:
    return _parse_anchors(
        html,
        source="NMPA",
        agency="NMPA",
        min_title_len=10,
        base_url=base_url,
        limit=8,
    )


def crawl_nmpa() -> dict:
    """先尝试公告通稿, 再尝试药品首页. 全部失败 → 静态兜底."""
    for url in [
        "https://www.nmpa.gov.cn/yaopin/ypggtg/index.html",  # 公告通稿 (含 OTC 转换 / 说明书修订)
        "https://www.nmpa.gov.cn/yaopin/",                   # 药品首页
    ]:
        try:
            html = _live_fetch(url)
            items = _parser(html, url)
            if items:
                result = _persist_items(items)
                return {"count": result["new"], "updated": result["updated"], "mode": "live", "url": url}
        except Exception:
            pass

    return run_with_static_fallback(
        name="NMPA",
        live_urls=[],
        static_items=STATIC_NMPA_ALERTS,
        parser=_parser,
    )
