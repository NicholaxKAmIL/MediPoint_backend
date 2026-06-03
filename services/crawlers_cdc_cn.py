"""
中国疾病预防控制中心 (www.chinacdc.cn) 真实爬虫
- 全国法定传染病疫情概况 (健康数据 → jksj01/) — 月度甲乙丙类传染病数据
- 流感监测周报 (健康数据 → jksj04_14249/) — 每周流感样病例 (ILI%) / 阳性率
- URL 模式: ./YYYYMM/t{YYYYMMDD}_{id}.html  (与 FJ WJW 相同)
- 详情页正文容器: <div id="articleCon"> ... <div class="trs_editor_view ...">
"""
from __future__ import annotations
import logging
import re
import sys
import pathlib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pymongo import UpdateOne

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
from db.mongo import db  # noqa: E402

log = logging.getLogger(__name__)

BASE_URL = "https://www.chinacdc.cn"

# 多个独立 sub-source (用 source_agency 区分; source 字段统一为 CN_CDC 便于 dashboard/regulations 分组)
CDC_SOURCES = {
    "monthly_report": {
        "label": "全国法定传染病疫情概况",
        "list_url": f"{BASE_URL}/jksj/jksj01/index.html",
        "category": "疫情月报",
        "default_risk": "Medium",
        "agency": "中国疾控中心",
        "risk_keywords_high": ["死亡", "暴发", "聚集", "重症"],
        "risk_keywords_medium": ["上升", "增加", "高峰", "预警", "流行", "扩散", "ILI%"],
    },
    "flu_weekly": {
        "label": "流感监测周报",
        "list_url": f"{BASE_URL}/jksj/jksj04_14249/index.html",
        "category": "流感周报",
        "default_risk": "Medium",
        "agency": "中国疾控中心 · 流感监测",
        "risk_keywords_high": ["死亡", "重症", "暴发", "聚集性"],
        "risk_keywords_medium": ["上升", "增加", "高峰", "阳性率", "ILI%", "流行", "扩散"],
    },
}

MEDICAL_KEYWORDS = [
    "传染病", "疫情", "流感", "流感样", "诺如", "手足口", "新冠", "登革热", "猴痘",
    "疫苗", "接种", "免疫",
    "药品", "处方", "药师", "药店",
    "药品召回", "召回", "不良反应",
    "中医", "中医药",
    "疾控", "疾控中心",
    "抗病毒", "奥司他韦",
    "防控", "ILI",
    "甲乙类", "丙类",
    "呼吸道", "肠道",
    "监测", "阳性率",
]

NEGATIVE_KEYWORDS = [
    "招聘", "考录", "拟录用", "招标", "中标", "采购公告",
    "工作要点", "培训通知", "会议通知",
    "版权", "免责",
    "声明",
]


def _http_get(url: str, timeout: int = 10) -> str:
    r = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=timeout,
    )
    r.raise_for_status()
    # chinanet CDC returns proper utf-8 in Content-Type, but be safe with apparent
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _is_relevant(title: str) -> bool:
    if any(neg in title for neg in NEGATIVE_KEYWORDS):
        return False
    return any(k in title for k in MEDICAL_KEYWORDS)


def _classify_risk(title: str, summary: str, cfg: dict, default: str) -> str:
    text = f"{title} {summary}"
    if any(k in text for k in cfg["risk_keywords_high"]):
        return "High"
    if any(k in text for k in cfg["risk_keywords_medium"]):
        return "Medium"
    return default


def _date_to_iso(compact: str) -> datetime | None:
    if not compact or len(compact) != 8:
        return None
    try:
        return datetime.strptime(compact, "%Y%m%d")
    except ValueError:
        return None


def _parse_list_page(html: str, list_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    for a in soup.select("a[href*='t20']"):
        href = a.get("href", "").strip()
        # 标题优先取 title 属性, 否则取文本 (但要剔除内嵌的 date span)
        title_attr = (a.get("title") or "").strip()
        if not title_attr:
            # 复制 a 节点, 移除内部 span, 再取文本
            a_copy = BeautifulSoup(str(a), "lxml").find("a")
            for span in a_copy.find_all("span"):
                span.decompose()
            title_attr = a_copy.get_text(strip=True)
        title = re.sub(r"\s+", " ", title_attr).strip()
        # 剔除尾部 "YYYY-MM-DD" 形式
        title = re.sub(r"\s*\d{4}-\d{2}-\d{2}\s*$", "", title).strip()
        if not href or not title or len(title) < 4:
            continue
        full_url = urljoin(list_url, href)
        m = re.search(r"t(\d{8})_", href)
        date_compact = m.group(1) if m else ""
        items.append({"title": title, "url": full_url, "date_compact": date_compact})
    return items


def _fetch_summary(url: str, max_chars: int = 600) -> str:
    try:
        html = _http_get(url, timeout=8)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # China CDC content container: <div id="articleCon">
    article = soup.select_one("#articleCon")
    if not article:
        article = soup.select_one("div.trs_editor_view")
    if not article:
        article = soup.select_one("article") or soup.select_one("main")
    if not article:
        return ""
    for tag in article(["script", "style"]):
        tag.decompose()
    text = article.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def _persist_batch(sliced: list[dict], summaries: dict[str, str]) -> dict:
    urls = [it["url"] for it in sliced]
    existing = {d["url"] for d in db.alerts.find({"url": {"$in": urls}}, {"url": 1})}
    new_items, existing_items = [], []
    for it in sliced:
        (new_items if it["url"] not in existing else existing_items).append(it)

    if new_items:
        db.alerts.insert_many([
            {**it, "summary": summaries.get(it["url"], "")} for it in new_items
        ])

    if existing_items:
        ops = [
            UpdateOne(
                {"url": it["url"]},
                {"$set": {
                    "title": it["title"],
                    "summary": summaries.get(it["url"], ""),
                    "published_at": it.get("published_at"),
                    "risk_level": it.get("risk_level"),
                    "category": it.get("category"),
                    "type": it.get("type"),
                    "source_agency": it.get("source_agency"),
                    "crawled_at": datetime.utcnow(),
                }},
            ) for it in existing_items
        ]
        db.alerts.bulk_write(ops, ordered=False)
    return {"new": len(new_items), "updated": len(existing_items)}


def crawl_cdc_cn_sub(key: str, limit: int = 10) -> dict:
    """抓取单个 sub-source (monthly_report / flu_weekly)."""
    cfg = CDC_SOURCES[key]
    list_url = cfg["list_url"]
    try:
        html = _http_get(list_url)
        items = _parse_list_page(html, list_url)
    except Exception as e:
        log.warning("[CN_CDC:%s] fetch failed: %s", key, e)
        return {"count": 0, "total_seen": 0, "error": str(e)}

    items = [it for it in items if _is_relevant(it["title"])][:limit]
    if not items:
        return {"count": 0, "total_seen": 0}

    with ThreadPoolExecutor(max_workers=5) as ex:
        summaries_list = list(ex.map(_fetch_summary, [it["url"] for it in items]))
    summaries = dict(zip([it["url"] for it in items], summaries_list))

    for it in items:
        it.update({
            "source": "CN_CDC",
            "source_agency": cfg["agency"],
            "agency": cfg["agency"],
            "category": cfg["category"],
            "type": cfg["category"],
            "risk_level": cfg["default_risk"],
            "published_at": _date_to_iso(it["date_compact"]),
            "crawled_at": datetime.utcnow(),
            "crawled_via": "live",
        })
        it["risk_level"] = _classify_risk(it["title"], summaries[it["url"]], cfg, it["risk_level"])

    result = _persist_batch(items, summaries)
    return {"count": result["new"], "updated": result["updated"], "total_seen": len(items)}


def crawl_cdc_cn_monthly(limit: int = 10) -> dict:
    return crawl_cdc_cn_sub("monthly_report", limit)


def crawl_cdc_cn_flu(limit: int = 8) -> dict:
    return crawl_cdc_cn_sub("flu_weekly", limit)
