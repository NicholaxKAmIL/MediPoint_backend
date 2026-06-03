"""
趋势分析 — 关键词热度 + 7 日时序聚合
- 数据源: db.alerts (政府公告) + db.raw_articles (微博/小红书/PTT/...)
- 关键词抽取: jieba 切词 + 实体词典过滤, 避免无意义高频词
- 缓存: 进程内 5 分钟 TTL, 减少 Mongo aggregate 压力
"""
from __future__ import annotations
import logging
import re
import sys
import pathlib
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from services.entity_keywords import ALL as ENTITY_WORDS  # noqa: E402

log = logging.getLogger(__name__)

# 简单停用词
STOPWORDS = {
    "的", "了", "是", "在", "和", "与", "及", "或", "等", "等", "月", "日", "年",
    "关于", "发布", "通知", "公告", "工作", "开展", "进行", "做好", "加强",
    "本", "本省", "全省", "全国", "要求", "应当", "可以", "需要", "通过",
    "为", "对", "从", "到", "向", "由", "以", "等", "每", "一次", "一", "二",
    "三", "四", "五", "六", "七", "八", "九", "十", "上", "下", "中", "内",
    "前", "后", "时", "期", "间", "例", "人", "名", "例", "份", "项",
    "近日", "目前", "现", "今", "去年", "今年", "明年", "上周", "本周", "下周",
    "月报", "周报", "年报", "日报",
}

# 来源归并 (raw_articles 已有 PTT/Dcard/GoogleNews; alerts 全归 GovNotice)
SOURCE_GROUPS = {"GovNotice", "Weibo", "Xiaohongshu", "PTT", "Dcard", "GoogleNews"}

_CACHE: dict = {}
_CACHE_TTL = 300  # 5 minutes


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if not hit:
        return None
    if time.time() - hit["t"] > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return hit["v"]


def _cache_set(key: str, v):
    _CACHE[key] = {"t": time.time(), "v": v}


def _iter_docs(days: int) -> list[dict]:
    """把 alerts + raw_articles 拉到一个 list, 每条带 source 和 text。"""
    since = datetime.utcnow() - timedelta(days=days)
    out: list[dict] = []
    for d in db.alerts.find({"crawled_at": {"$gte": since}}):
        out.append({
            "source": "GovNotice",
            "text": f"{d.get('title', '')} {d.get('summary', '')}",
            "crawled_at": d.get("crawled_at"),
        })
    for d in db.raw_articles.find({"crawled_at": {"$gte": since}}):
        out.append({
            "source": d.get("source", "Internet"),
            "text": f"{d.get('title', '')} {d.get('content', '')}",
            "crawled_at": d.get("crawled_at"),
        })
    return out


def compute_keyword_trend(days: int = 7, top_n: int = 7) -> list[dict]:
    """返回 [{keyword, value, change_pct}] — 实体词典优先, 不足时回退 jieba 通用词。"""
    cache_key = f"kw:{days}:{top_n}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    docs = _iter_docs(days)
    if len(docs) < 3:
        return []

    import jieba
    sorted_entities = sorted(set(ENTITY_WORDS), key=lambda x: -len(x))
    counter: Counter = Counter()
    for d in docs:
        text = d["text"]
        masked = text
        for kw in sorted_entities:
            if kw and kw in masked:
                counter[kw] += masked.count(kw)
                masked = masked.replace(kw, " " * len(kw))
        if len(counter) < top_n:
            for w in jieba.cut(masked):
                w = w.strip()
                if len(w) < 2 or len(w) > 8:
                    continue
                if w in STOPWORDS:
                    continue
                if not re.search(r"[\u4e00-\u9fa5A-Za-z0-9]", w):
                    continue
                counter[w] += 1

    if not counter:
        _cache_set(cache_key, [])
        return []

    prev_docs = _iter_docs(days * 2)
    has_prev = len(prev_docs) > len(docs)
    prev_text = " ".join(d["text"] for d in prev_docs[:-len(docs)]) if has_prev else ""
    prev_counts: Counter = Counter()
    if prev_text:
        prev_masked = prev_text
        for kw in sorted_entities:
            if kw and kw in prev_masked:
                prev_counts[kw] += prev_masked.count(kw)
                prev_masked = prev_masked.replace(kw, " " * len(kw))

    top = counter.most_common(top_n)
    out = []
    for kw, value in top:
        prev = prev_counts.get(kw, 0)
        if not has_prev:
            change = 0
        elif prev > 0:
            change = round((value - prev) / prev * 100)
        else:
            change = 100 if value > 0 else 0
        out.append({"keyword": kw, "value": int(value), "change_pct": change})

    _cache_set(cache_key, out)
    return out


def compute_seven_day_series(days: int = 7) -> list[dict]:
    """返回 [{date, Weibo, Xiaohongshu, GovNotice}, ...] 按日期升序。"""
    cache_key = f"series:{days}"
    hit = _cache_get(cache_key)
    if hit is not None:
        return hit

    docs = _iter_docs(days)
    if not docs:
        return []

    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {
        "Weibo": 0, "Xiaohongshu": 0, "GovNotice": 0, "PTT": 0, "Dcard": 0, "GoogleNews": 0,
    })
    for d in docs:
        ts = d.get("crawled_at")
        if not ts:
            continue
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                continue
        day = ts.strftime("%m-%d")
        src = d["source"]
        if src in buckets[day]:
            buckets[day][src] += 1

    out = []
    for day in sorted(buckets.keys()):
        row = {"date": day}
        row.update(buckets[day])
        out.append(row)
    _cache_set(cache_key, out)
    return out
