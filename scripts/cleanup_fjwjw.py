"""
一次性清理脚本: 
1. 重新评估 db.alerts 中所有 FJ_WJW 条目, 删除不再命中的 (新 filter 下应丢弃的)
2. 对保留的条目, 重新抓取 summary (用 TRS_Editor 替换原 nav-text)
3. 重新分类 risk_level

可重复运行 (idempotent).
"""
import sys
import pathlib
import logging

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from db.mongo import db  # noqa: E402
from services.crawlers_fjwjw import (  # noqa: E402
    _is_medical, _classify_risk, _fetch_summary,
)

log = logging.getLogger("cleanup")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    items = list(db.alerts.find({"source": "FJ_WJW"}))
    kept, dropped, refreshed = 0, 0, 0
    for it in items:
        title = it.get("title", "")
        if not _is_medical(title):
            db.alerts.delete_one({"_id": it["_id"]})
            dropped += 1
            log.info("dropped: %s", title[:50])
            continue
        # 重新抓 summary + 分类
        new_summary = _fetch_summary(it["url"])
        new_risk = _classify_risk(title, new_summary, it.get("risk_level", "Medium"))
        # 只在有变化时写
        if new_summary and new_summary != it.get("summary", ""):
            refreshed += 1
        db.alerts.update_one(
            {"_id": it["_id"]},
            {"$set": {
                "summary": new_summary or it.get("summary", ""),
                "risk_level": new_risk,
            }},
        )
        kept += 1
    log.info("done: kept=%d dropped=%d summaries_refreshed=%d", kept, dropped, refreshed)


if __name__ == "__main__":
    main()
