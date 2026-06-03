"""
FJ CDC 真实爬虫 (带静态 cache 兜底)
- 真实抓取:
  - 优先: 疫情公告 (/xxgklist?ctlgid=415273) — 与药品零售强相关
  - 兜底: 健康教育 (/jkjy_list?ctlgid=644621)
- 失败时: 静态 cache 兜底
- 页面结构: <li><a href="/show?ctlgid=...&Id=...">title</a><span>YYYY-MM-DD</span></li>
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
from services._crawler_base import _persist_items, run_with_static_fallback  # noqa: E402
from services.static_cache_fjcdc import STATIC_FJCDC_ALERTS  # noqa: E402

log = logging.getLogger(__name__)

BASE_URL = "https://www.fjcdc.com.cn"

FJCDC_LIVE_URLS = [
    f"{BASE_URL}/xxgklist?ctlgid=415273",  # 疫情公告 — 用户建议, 与药品零售强相关
    f"{BASE_URL}/jkjy_list?ctlgid=644621",  # 健康教育 (兜底)
]

MEDICAL_KEYWORDS = [
    "传染病", "疫情", "流感", "流感样", "诺如", "手足口", "登革热", "猴痘", "基孔肯雅",
    "疫苗", "接种", "免疫",
    "药品", "处方", "药师", "药店",
    "药品召回", "召回", "不良反应",
    "中医", "中医药",
    "疾控", "疾控中心",
    "抗病毒", "奥司他韦",
    "防控", "呼吸道", "肠道",
    "监测",
    "H5N6", "H7N9", "登革", "基孔肯雅",
    "公共卫生事件", "突发公共卫生",
    "ILI", "法定报告",
]

NEGATIVE_KEYWORDS = [
    "饮用水", "水箱", "水嘴", "管材",
    "拟设置", "设置医疗机构", "医疗机构设置",
    "卫生许可证", "卫生许可公示",
    "巡回宣讲", "红医精神", "主题宣讲",
    "征集报价", "结果公告", "招标", "中标", "采购公告",
    "信用评价", "信用公示",
    "抗蛇毒血清",
    "招聘", "考录", "拟录用",
    "代表建议", "政协提案", "建议提案",
    "工作要点", "培训通知", "会议通知",
    "妇幼", "母婴", "养老",
    "托幼", "学校卫生",
]


def _is_relevant(title: str) -> bool:
    if any(neg in title for neg in NEGATIVE_KEYWORDS):
        return False
    return any(k in title for k in MEDICAL_KEYWORDS)


def _http_get(url: str, timeout: int = 10) -> str:
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def _parse_list(html: str, list_url: str) -> list[dict]:
    """FJ CDC 专用解析: 只取 /show?ctlgid=...&Id=... 形式的详情链接 + 同 li 内的日期."""
    soup = BeautifulSoup(html, "lxml")
    items: list[dict] = []
    for li in soup.select("li"):
        a = li.find("a", href=re.compile(r"^/show\?"))
        if not a:
            continue
        href = a.get("href", "").strip()
        title = (a.get("title") or a.get_text() or "").strip()
        if not title or len(title) < 4:
            continue
        # 局部查找日期
        date_iso = None
        date_span = li.find(string=re.compile(r"\d{4}-\d{2}-\d{2}"))
        if date_span:
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", date_span)
            if m:
                try:
                    date_iso = datetime.strptime(m.group(0), "%Y-%m-%d")
                except ValueError:
                    pass
        items.append({
            "title": title,
            "url": urljoin(list_url, href),
            "date_compact": date_iso.strftime("%Y%m%d") if date_iso else "",
            "_date_iso": date_iso,
        })
    return items


def _classify_risk(title: str, summary: str, default: str) -> str:
    text = f"{title} {summary}"
    if any(k in text for k in ["死亡", "重症", "暴发", "聚集性", "一级召回", "突发公共卫生"]):
        return "High"
    if any(k in text for k in ["上升", "高峰", "增加", "聚集", "风险提示", "监测", "预警", "不良反应", "流行", "扩散", "ILI"]):
        return "Medium"
    return default


def _fetch_summary(url: str, max_chars: int = 500) -> str:
    try:
        html = _http_get(url, timeout=6)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    # FJ CDC 详情页正文 (尝试常见的容器)
    article = (
        soup.select_one("div.content")
        or soup.select_one("div#content")
        or soup.select_one("div.article")
        or soup.select_one("article")
        or soup.select_one("main")
    )
    if not article:
        article = soup.body or soup
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
                    "crawled_at": datetime.utcnow(),
                }},
            ) for it in existing_items
        ]
        db.alerts.bulk_write(ops, ordered=False)
    return {"new": len(new_items), "updated": len(existing_items)}


def crawl_fjcdc() -> dict:
    """FJ CDC: 优先 疫情公告, 否则 健康教育. 全部失败 → 静态兜底."""
    for list_url in FJCDC_LIVE_URLS:
        try:
            html = _http_get(list_url)
            raw_items = _parse_list(html, list_url)
            items = [it for it in raw_items if _is_relevant(it["title"])]
            if items:
                # 并行抓详情
                with ThreadPoolExecutor(max_workers=5) as ex:
                    summaries_list = list(ex.map(_fetch_summary, [it["url"] for it in items]))
                summaries = dict(zip([it["url"] for it in items], summaries_list))

                for it in items:
                    date_iso = it.pop("_date_iso", None)
                    it.update({
                        "source": "FJ_CDC",
                        "agency": "福建 CDC",
                        "category": "疫情公告" if "415273" in list_url else "健康教育",
                        "type": "公告",
                        "risk_level": "Medium",
                        "published_at": date_iso,
                        "crawled_at": datetime.utcnow(),
                        "crawled_via": "live",
                    })
                    it["risk_level"] = _classify_risk(it["title"], summaries[it["url"]], it["risk_level"])

                result = _persist_batch(items, summaries)
                return {
                    "count": result["new"],
                    "updated": result["updated"],
                    "mode": "live",
                    "url": list_url,
                    "total_seen": len(items),
                }
        except Exception as e:
            log.info("[FJ_CDC] live fetch %s failed: %s", list_url, e)

    # 全部失败 — 静态兜底
    return run_with_static_fallback(
        name="FJ_CDC",
        live_urls=[],
        static_items=STATIC_FJCDC_ALERTS,
        parser=lambda html, base_url: [],  # not used in fallback
    )
