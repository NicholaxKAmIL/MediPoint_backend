"""
FJ WJW (福建省卫健委) 真实爬虫 — 抓取疫情公告 / 通知公告
URL 模式: https://wjw.fujian.gov.cn/xxgk/gsgg/{cat}/{YYYYMM}/t{YYYYMMDD}_{id}.htm
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

BASE_URL = "https://wjw.fujian.gov.cn"
CATEGORIES = {
    "yqgg": {"path": "yqgg", "label": "疫情公告", "default_risk": "Medium"},
    "tzgg": {"path": "tzgg", "label": "通知公告", "default_risk": "Low"},
}

# 药品零售药店真正相关的主题词 (避免误抓 涉水产品/消毒产品/医疗机构公示 等)
MEDICAL_KEYWORDS = [
    "传染病", "疫情", "流感", "流感样", "诺如", "手足口", "新冠",
    "疫苗", "接种", "免疫",
    "药品", "处方", "药师", "药店", "零售药店", "处方药", "非处方药", "OTC",
    "药品召回", "召回", "不良反应", "监测",
    "中医", "中医药",
    "流感样病例", "ILI",
    "疾控", "疾控中心",
    "抗病毒", "奥司他韦",
    "防控", "防控工作", "防控通知", "防控指南",
    "法定报告",
]

# 明显与药品零售无关的关键词 (命中即丢弃)
NEGATIVE_KEYWORDS = [
    "涉水产品", "饮用水", "水箱", "管材", "水嘴",
    "消毒产品生产企业", "消毒产品卫生许可", "消毒剂生产",
    "拟设置医疗机构", "设置医疗机构", "医疗机构设置",
    "卫生许可证", "卫生许可公示", "卫生许可公告",
    "巡回宣讲", "红医精神", "主题宣讲",
    "征集报价", "结果公告", "招标", "中标", "采购公告",
    "信用评价", "信用公示",
    "抗蛇毒血清",
    "招聘", "考录", "拟录用",
    "代表建议", "政协提案", "建议提案",
    "评估报告", "绩效评价",
    "工作要点", "工作要点", "工作要点通知",
    "妇幼", "母婴", "养老",
    "托幼", "学校卫生",
]

# HIGH 优先匹配 (顺序重要); MEDIUM 收紧, 移除 "通知"/"发布" 这类过宽关键词
HIGH_RISK_KEYWORDS = ["死亡", "重症", "暴发", "聚集性", "一级召回", "突发公共卫生", "重症病例", "死亡病例"]
MEDIUM_RISK_KEYWORDS = ["上升", "高峰", "增加", "聚集", "风险提示", "监测", "预警", "不良反应", "流行", "扩散"]


def _http_get(url: str, timeout: int = 10) -> str:
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _classify_risk(title: str, summary: str, default: str) -> str:
    text = f"{title} {summary}"
    if any(k in text for k in HIGH_RISK_KEYWORDS):
        return "High"
    if any(k in text for k in MEDIUM_RISK_KEYWORDS):
        return "Medium"
    return default


def _is_medical(title: str) -> bool:
    """标题必须命中至少一个 MEDICAL_KEYWORDS, 且不能命中任何 NEGATIVE_KEYWORDS."""
    if any(neg in title for neg in NEGATIVE_KEYWORDS):
        return False
    return any(k in title for k in MEDICAL_KEYWORDS)


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
    for a in soup.select("li a[href*='t20']"):
        href = a.get("href", "").strip()
        title = (a.get("title") or a.get_text() or "").strip()
        if not href or not title:
            continue
        full_url = urljoin(list_url, href)
        m = re.search(r"t(\d{8})_", href)
        date_compact = m.group(1) if m else ""
        # 局部查找 (不重新搜索整文档)
        date_span = a.find("span", class_="bf-pass")
        if date_span and date_span.get_text(strip=True):
            date_compact = date_span.get_text(strip=True).replace("-", "")
        items.append({"title": title, "url": full_url, "date_compact": date_compact})
    return items


def _fetch_summary(url: str, max_chars: int = 600) -> str:
    """抓取详情页正文 (不是站点 nav/footer). FJ WJW 用 TRS 编辑器, 内容在 div.TRS_Editor."""
    try:
        html = _http_get(url, timeout=6)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "lxml")
    # FJ WJW 编辑器容器 — 真实正文, 不含站点 nav/footer
    article = soup.select_one("div.TRS_Editor")
    if not article:
        # 退路: 找 main / article 标签
        article = soup.select_one("article") or soup.select_one("main")
    if not article:
        return ""
    for tag in article(["script", "style"]):
        tag.decompose()
    text = article.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()[:max_chars]


def _persist_batch(sliced: list[dict], summaries: dict[str, str]) -> dict:
    """sliced 中含完整的元数据 (含 risk_level), summaries 是 url -> 详情 summary 映射."""
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
                    "crawled_at": datetime.utcnow(),
                }},
            ) for it in existing_items
        ]
        db.alerts.bulk_write(ops, ordered=False)

    return {"new": len(new_items), "updated": len(existing_items)}


def crawl_fjwjw_category(cat_key: str, limit: int = 10) -> dict:
    """统一入口 — 通过 cat_key 选 yqgg / tzgg"""
    cat = CATEGORIES[cat_key]
    list_url = f"{BASE_URL}/xxgk/gsgg/{cat['path']}/"
    try:
        html = _http_get(list_url)
        items = _parse_list_page(html, list_url)
    except Exception as e:
        log.warning("[FJ_WJW:%s] fetch failed: %s", cat_key, e)
        return {"count": 0, "total_seen": 0, "error": str(e)}

    items = [it for it in items if _is_medical(it["title"])][:limit]
    if not items:
        return {"count": 0, "total_seen": 0}

    # 并行抓详情
    with ThreadPoolExecutor(max_workers=5) as ex:
        summaries_list = list(ex.map(_fetch_summary, [it["url"] for it in items]))
    summaries = dict(zip([it["url"] for it in items], summaries_list))

    # 元数据 + 风险分类 (用真实 summary)
    for it in items:
        it.update({
            "source": "FJ_WJW",
            "agency": "福建省卫健委",
            "category": cat["label"],
            "type": cat["label"],
            "risk_level": cat["default_risk"],
            "published_at": _date_to_iso(it["date_compact"]),
            "crawled_at": datetime.utcnow(),
            "crawled_via": "live",
        })
        it["risk_level"] = _classify_risk(it["title"], summaries[it["url"]], it["risk_level"])

    result = _persist_batch(items, summaries)
    return {"count": result["new"], "updated": result["updated"], "total_seen": len(items)}


def crawl_fjwjw_yqgg(limit: int = 10) -> dict:
    return crawl_fjwjw_category("yqgg", limit)


def crawl_fjwjw_tzgg(limit: int = 10) -> dict:
    return crawl_fjwjw_category("tzgg", limit)
