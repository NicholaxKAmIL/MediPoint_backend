"""
RAG 主入口:
- reindex_all(): 拉取 alerts + drug_monographs + sop_entries + CHAT_FAQ, 重建索引
- retrieve(): 检索 top_k
"""
from __future__ import annotations

import logging
import sys
import pathlib
import threading
import time

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from services.mock_data import CHAT_FAQ  # noqa: E402
from services.rag_retriever import retriever  # noqa: E402
from services import seed_kb  # noqa: E402

log = logging.getLogger(__name__)

_lock = threading.RLock()
_last_index_meta: dict = {}


def _alert_to_chunks(alert: dict) -> list[dict]:
    title = alert.get("title", "")
    summary = alert.get("summary", "")
    aid = str(alert.get("_id", ""))
    return [{
        "id": f"alert-{aid}",
        "text": f"{title}。{summary}".strip("。 "),
        "metadata": {
            "source_type": "alert",
            "title": title,
            "url": alert.get("url", ""),
            "agency": alert.get("agency") or alert.get("source", ""),
            "risk_level": alert.get("risk_level", "Medium"),
            "alert_id": aid,
        },
    }]


def _drug_to_chunks(drug: dict) -> list[dict]:
    name = drug.get("drug_name", "")
    base = f"drug-{name}"
    return [
        {
            "id": f"{base}-ind",
            "text": f"{name} 适应症: {drug.get('indications', '')}",
            "metadata": {
                "source_type": "drug",
                "drug_name": name,
                "section": "适应症",
                "title": name,
            },
        },
        {
            "id": f"{base}-dos",
            "text": f"{name} 用法用量: {drug.get('dosage', '')}",
            "metadata": {
                "source_type": "drug",
                "drug_name": name,
                "section": "用法用量",
                "title": name,
            },
        },
        {
            "id": f"{base}-con",
            "text": f"{name} 禁忌 / 不良反应: {drug.get('contraindications', '')} {drug.get('side_effects', '')}",
            "metadata": {
                "source_type": "drug",
                "drug_name": name,
                "section": "禁忌",
                "title": name,
            },
        },
    ]


def _sop_to_chunks(sop: dict) -> list[dict]:
    title = sop.get("title", "")
    return [{
        "id": f"sop-{title}",
        "text": f"{title}。场景: {sop.get('scenario', '')}。步骤: {sop.get('steps', '')}",
        "metadata": {
            "source_type": "sop",
            "title": title,
            "scenario": sop.get("scenario", ""),
        },
    }]


def _faq_to_chunks(faq: dict, idx: int) -> list[dict]:
    patterns = faq.get("patterns", []) or []
    return [{
        "id": f"faq-{idx}",
        "text": f"问题关键词: {' '.join(patterns)}\n答案: {faq.get('answer', '')}\n来源: {faq.get('source', '')}",
        "metadata": {
            "source_type": "faq",
            "patterns": patterns,
            "title": faq.get("source", ""),
        },
    }]


def reindex_all() -> dict:
    """全量重建索引。返回元数据。"""
    with _lock:
        t0 = time.time()
        chunks: list[dict] = []

        alerts_added = 0
        try:
            for a in db.alerts.find():
                a["_id"] = str(a.get("_id", ""))
                chunks.extend(_alert_to_chunks(a))
                alerts_added += 1
        except Exception as e:
            log.warning("reindex_all: 读 alerts 失败: %s", e)

        drugs = seed_kb.get_all_drugs()
        drugs_added = 0
        for d in drugs:
            chunks.extend(_drug_to_chunks(d))
            drugs_added += 1

        sops = seed_kb.get_all_sops()
        sops_added = 0
        for s in sops:
            chunks.extend(_sop_to_chunks(s))
            sops_added += 1

        faqs_added = 0
        for i, faq in enumerate(CHAT_FAQ):
            chunks.extend(_faq_to_chunks(faq, i))
            faqs_added += 1

        n = retriever.index(chunks)
        duration = round(time.time() - t0, 3)
        meta = {
            "indexed": n,
            "alerts": alerts_added,
            "drugs": drugs_added,
            "sops": sops_added,
            "faqs": faqs_added,
            "duration_s": duration,
        }
        _last_index_meta.update(meta)
        log.info("reindex_all done: %s", meta)
        return meta


def retrieve(query: str, top_k: int = 5, source_types: list[str] | None = None) -> list[dict]:
    """检索 top_k 相似 chunk。"""
    if not query or not query.strip():
        return []
    return retriever.search(query, top_k=top_k, source_type_filter=source_types)


def get_stats() -> dict:
    return {
        "size": retriever.size,
        "last_index": dict(_last_index_meta),
    }
