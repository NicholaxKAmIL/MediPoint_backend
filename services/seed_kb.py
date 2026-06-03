"""
知识库种子数据 — 启动时灌入静态药品说明书 + SOP (幂等)。
- 仅在对应 collection 完全为空时写入。
- 重复运行不会重复插入。
"""
from __future__ import annotations

import logging
import sys
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from services import data_drug_monographs, data_sops  # noqa: E402

log = logging.getLogger(__name__)


def _seed_drug_monographs() -> int:
    if db.drug_monographs.count_documents({}) > 0:
        return 0
    docs = [
        {
            "drug_name": d["drug_name"],
            "category": d["category"],
            "indications": d["indications"],
            "dosage": d["dosage"],
            "side_effects": d["side_effects"],
            "contraindications": d["contraindications"],
            "source": d["source"],
        }
        for d in data_drug_monographs.DRUGS
    ]
    db.drug_monographs.insert_many(docs)
    return len(docs)


def _seed_sop_entries() -> int:
    if db.sop_entries.count_documents({}) > 0:
        return 0
    docs = [
        {
            "title": s["title"],
            "scenario": s["scenario"],
            "steps": s["steps"],
            "source": s["source"],
        }
        for s in data_sops.SOPS
    ]
    db.sop_entries.insert_many(docs)
    return len(docs)


def seed_if_empty() -> dict:
    """启动时调用, 灌入静态 KB 数据。返回每类条数。"""
    try:
        drugs = _seed_drug_monographs()
        sops = _seed_sop_entries()
        if drugs or sops:
            log.info("seed_kb: drugs=%d sops=%d", drugs, sops)
        return {"drugs": drugs, "sops": sops}
    except Exception as e:
        log.warning("seed_kb failed (likely Mongo offline): %s", e)
        return {"drugs": 0, "sops": 0, "error": str(e)}


def get_all_drugs() -> list[dict]:
    """优先读 Mongo, 空则用静态数据 (保证索引可建)。"""
    rows = list(db.drug_monographs.find())
    if rows:
        for r in rows:
            r["_id"] = str(r["_id"])
        return rows
    return [
        {
            "drug_name": d["drug_name"],
            "category": d["category"],
            "indications": d["indications"],
            "dosage": d["dosage"],
            "side_effects": d["side_effects"],
            "contraindications": d["contraindications"],
            "source": d["source"],
        }
        for d in data_drug_monographs.DRUGS
    ]


def get_all_sops() -> list[dict]:
    rows = list(db.sop_entries.find())
    if rows:
        for r in rows:
            r["_id"] = str(r["_id"])
        return rows
    return [
        {
            "title": s["title"],
            "scenario": s["scenario"],
            "steps": s["steps"],
            "source": s["source"],
        }
        for s in data_sops.SOPS
    ]
