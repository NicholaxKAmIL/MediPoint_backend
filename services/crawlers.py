"""
MediPoint 爬蟲 (中國福建地區) — 骨架階段
- 福建 CDC (http://www.fjcdc.com.cn)  — 暫不啟用真實爬取
- NMPA (https://www.nmpa.gov.cn)      — 待添加
- 福建省衛健委 (http://wjw.fujian.gov.cn) — 待添加

說明：台灣 PTT / Dcard 已停止維護, 後續將以福建政府公開數據為主。
當前僅作為運行入口存在, 真實抓取 / 入庫邏輯實作後再開啟。
"""

from datetime import datetime

FUJIAN_SOURCES = [
    {"name": "FJ_CDC", "url": "http://www.fjcdc.com.cn/", "agency": "福建 CDC"},
    {"name": "FJ_WJW", "url": "http://wjw.fujian.gov.cn/", "agency": "福建省衛健委"},
    {"name": "NMPA",   "url": "https://www.nmpa.gov.cn/", "agency": "NMPA"},
]


def _skeleton(name: str) -> int:
    """骨架佔位 — 不寫入任何集合, 僅列印進度以保留可觀測性。"""
    print(f"[{name}] Skeleton — real fetch not yet implemented.")
    return 0


def crawl_fjcdc(limit=5) -> list:
    return []  # placeholder; real implementation will return parsed alerts


def crawl_fj_wjw(limit=5) -> list:
    return []


def crawl_nmpa(limit=5) -> list:
    return []


def run_all_crawlers() -> dict:
    """統一入口: 啟用福建地區政府公開數據爬蟲 (骨架階段無實際抓取)。"""
    _skeleton("FJ-CDC")
    _skeleton("FJ-WJW")
    _skeleton("NMPA")
    return {"fjcdc": 0, "fj_wjw": 0, "nmpa": 0}
