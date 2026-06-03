"""
MediPoint 爬虫统一入口
- 5 个 source 并行执行 (ThreadPoolExecutor)
- 每个 source 独立失败/降级
- 写结果到 crawler_status
"""
from __future__ import annotations
import logging
import sys
import pathlib
from concurrent.futures import ThreadPoolExecutor

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))

from services.crawlers_fjwjw import crawl_fjwjw_yqgg, crawl_fjwjw_tzgg  # noqa: E402
from services.crawlers_fjcdc import crawl_fjcdc  # noqa: E402
from services.crawlers_nmpa import crawl_nmpa  # noqa: E402
from services.crawlers_cdc_cn import crawl_cdc_cn_monthly, crawl_cdc_cn_flu  # noqa: E402
from services.crawler_status import update as update_status  # noqa: E402

log = logging.getLogger(__name__)

_JOBS = [
    ("fjwjw_yqgg", crawl_fjwjw_yqgg),
    ("fjwjw_tzgg", crawl_fjwjw_tzgg),
    ("fjcdc", crawl_fjcdc),
    ("nmpa", crawl_nmpa),
    ("cdc_cn_monthly", crawl_cdc_cn_monthly),
    ("cdc_cn_flu", crawl_cdc_cn_flu),
]


def run_all_crawlers() -> dict:
    """统一入口: 6 个 source 并行调用。"""
    results: dict = {}
    errors: list[str] = []

    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = {ex.submit(fn): name for name, fn in _JOBS}
        for fut, name in futures.items():
            try:
                results[name] = fut.result()
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
                results[name] = {"count": 0, "error": str(e)}

    update_status(results, errors)
    return results
