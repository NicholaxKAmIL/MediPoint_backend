from fastapi import APIRouter

from services.crawler_status import get_status

router = APIRouter(prefix="/api/crawler", tags=["Crawler"])


@router.get("/status")
def crawler_status():
    """最近一次爬虫执行的结果 + 时间。"""
    return get_status()
