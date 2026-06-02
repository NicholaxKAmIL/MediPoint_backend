from db.mongo import db
from util.gemini import generate_talking_point
from util.config import Env
from services import mock_data
from datetime import datetime

TARGET_DATE = "2025-10-30"
STORE_ID = "S001"

def get_weekly_dashboard_data():
    """
    處理 Dashboard 所有的資料獲取與計算邏輯
    當 ENABLE_MOCK=true 時直接回傳全量模擬資料 (中國福建地區)
    """
    if Env.ENABLE_MOCK:
        return mock_data.dashboard_payload()

    # ==========================================
    # 1. 計算 KPI (從 daily_category_summary 撈取)
    # ==========================================
    pipeline_kpi = [
        {"$match": {"date": TARGET_DATE, "store_id": STORE_ID}},
        {"$group": {
            "_id": None,
            "total_revenue": {"$sum": "$revenue"},
            "total_gp": {"$sum": "$gross_profit"}
        }}
    ]
    
    kpi_result = list(db.daily_category_summary.aggregate(pipeline_kpi))
    
    if kpi_result:
        revenue = kpi_result[0]['total_revenue']
        gp = kpi_result[0]['total_gp']
        margin = round((gp / revenue) * 100, 1) if revenue > 0 else 0
    else:
        revenue = 42296
        gp = 4148
        margin = 9.8

    kpi_data = {
        "coverage_label": "熱門商品覆蓋率",
        "coverage_value": "85%",
        "coverage_trend": "較上週 +5%",
        "coverage_progress": 85,
        "gross_profit": f"{int(gp):,}",
        "margin_rate": f"{margin}%",
        "margin_status": "low" if margin < 15 else "high",
        "top_category": "保健藥品"
    }

    # ==========================================
    # 2. 取得法規警示
    # ==========================================
    alert_cursor = db.alerts.find().sort("crawled_at", -1).limit(5)
    alerts = []
    
    for a in alert_cursor:
        alerts.append({
            "agency": a.get("agency", "CDC"),
            "type": a.get("type", "公告"),
            "title": a.get("title", "無標題"),
            "risk_level": a.get("risk_level", "Medium")
        })
        
    if not alerts:
        alerts = [
            {"agency": "CDC", "type": "系統提示", "title": "尚無最新疫情警示資料，請至後端執行爬蟲更新。", "risk_level": "Low"},
            {"agency": "TFDA", "type": "範例", "title": "特定批號胃藥因包裝瑕疵啟動二級回收 (範例)", "risk_level": "Medium"}
        ]

    # ==========================================
    # 3. 產生智慧備貨建議
    # ==========================================
    low_stock_cursor = db.inventory.find({
        "date": TARGET_DATE, 
        "store_id": STORE_ID,
        "closing_on_hand": {"$lt": 30}
    }).limit(2)

    high_stock_cursor = db.inventory.find({
        "date": TARGET_DATE, 
        "store_id": STORE_ID,
        "closing_on_hand": {"$gt": 100}
    }).limit(1)
    
    suggestions = []

    # 3.1 補貨建議
    restock_items = []
    for item in low_stock_cursor:
        sku_name = f"熱銷藥品 ({item['sku_id'][-3:]})"
        if "保健" in item['sku_id']: sku_name = f"綜合感冒藥 ({item['sku_id'][-3:]})"
        if "婦嬰" in item['sku_id']: sku_name = f"兒童退燒水 ({item['sku_id'][-3:]})"

        restock_items.append({
            "sku_id": item["sku_id"],
            "name": sku_name,
            "stock": item["closing_on_hand"],
            "margin": 34.1, 
            "sales_7d": 14,
            "status": "Critical"
        })
    
    if restock_items:
        ai_talk = generate_talking_point("流感高峰", [x['name'] for x in restock_items], "庫存告急")
        suggestions.append({
            "topic": "流感與呼吸道感染高峰",
            "action": "Restock",
            "related_category": "感冒/退燒",
            "reason": "輿情熱度上升 150%，且店內庫存低於安全水位。",
            "items": restock_items,
            "talking_points": ai_talk
        })

    # 3.2 促銷建議
    promo_items = []
    for item in high_stock_cursor:
         promo_items.append({
            "sku_id": item["sku_id"],
            "name": f"維他命/噴劑 ({item['sku_id'][-3:]})",
            "stock": item["closing_on_hand"],
            "margin": 36.0,
            "sales_7d": 5,
            "status": "Safe"
        })

    if promo_items:
        suggestions.append({
            "topic": "換季過敏潮",
            "action": "Promotion",
            "related_category": "鼻噴劑/維他命",
            "reason": "網路討論增加，但店內庫存過高，建議做促銷去化。",
            "items": promo_items,
            "talking_points": "雖然現在有人問，但庫存偏高。建議搭配維他命 C 做「換季防護組」促銷。"
        })

    # ==========================================
    # 4. 輿情 (配額制：各平台取最新 5 筆)
    # ==========================================
    insights = []
    
    # 定義要抓取的來源與數量
    target_sources = ["PTT", "Dcard", "GoogleNews"]
    
    for source in target_sources:
        # 針對每個來源，依時間排序抓最新的 5 筆
        cursor = db.raw_articles.find({"source": source}).sort("crawled_at", -1).limit(5)
        
        for art in cursor:
            # 標籤邏輯
            tags = ["熱議"]
            title = art.get("title", "")
            if "感冒" in title or "流感" in title: tags.append("流感")
            if "缺" in title: tags.append("缺貨")
            if "藥" in title: tags.append("用藥諮詢")
            if "寶寶" in title or "小孩" in title: tags.append("兒童")
            
            insights.append({
                "source": art.get("source", "Internet"),
                "board": art.get("board", "General"),
                "title": title,
                "content": art.get("content", "")[:60] + "...", 
                "url": art.get("url", "#"),
                "intent": "Ask" if "?" in title else "Complain",
                "tags": tags,
                # 雖然現在是分開抓，但加上時間欄位方便前端如果要統一排序
                "crawled_at": art.get("crawled_at") 
            })

    # 如果 DB 真的全空，才給 Mock Data
    if not insights:
        insights = [
            {"source": "PTT", "board": "BabyMother", "title": "(範例) 小孩半夜發燒買不到藥怎麼辦？", "content": "跑了兩家藥局都說退燒藥缺貨...", "url": "#", "intent": "Out_of_Stock", "tags": ["缺貨", "兒童"]},
            {"source": "Dcard", "board": "Health", "title": "(範例) 最近流感是不是很強？", "content": "吞口水像刀割一樣...", "url": "#", "intent": "Ask", "tags": ["流感", "推薦"]}
        ]

    return {
        "report_date": TARGET_DATE,
        "kpiData": kpi_data,
        "alerts": alerts,
        "suggestions": suggestions,
        "insights": insights
    }