from fastapi import APIRouter, BackgroundTasks
# 注意這裡改成 services.crawlers
from services.crawlers import run_all_crawlers

router = APIRouter(prefix="/api/crawler", tags=["Crawler"])

@router.post("/run")
async def run_crawlers_background(background_tasks: BackgroundTasks):
    """
    手動觸發福建地區爬蟲 (福建 CDC / 福建衛健委 / NMPA)
    """
    background_tasks.add_task(run_all_crawlers)
    return {"message": "福建地區爬蟲任務已啟動", "status": "processing"}
