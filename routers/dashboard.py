from fastapi import APIRouter, Query
from services.dashboard import get_weekly_dashboard_data

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

@router.get("/weekly-report")
def get_weekly_report(store: str = Query("S001", description="门店 ID")):
    """
    取得本週戰情摘要 (KPI / 建議 / 輿情)
    真实模式从 Mongo 聚合, 无数据时降级为 mock_data 保证 demo 不挂
    """
    return get_weekly_dashboard_data(store_id=store)