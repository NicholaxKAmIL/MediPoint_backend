import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
import random
import cloudscraper
import re
import sys
from db.mongo import db

# --- 設定 Headers ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
PTT_COOKIES = {"over18": "1"} 

PTT_TARGET_BOARDS = ["BabyMother", "Health", "Beauty", "Gossiping"]

# --- 健康與藥品關鍵字篩選 ---
HEALTH_KEYWORDS = [
    # 疾病症狀
    "感冒", "發燒", "咳嗽", "流感", "腸病毒", "過敏", "氣喘", "鼻炎", "喉嚨痛", "頭痛",
    "腹瀉", "便秘", "腸胃", "胃痛", "噁心", "嘔吐", "疲勞", "失眠", "焦慮", "憂鬱",
    "高血壓", "糖尿病", "癌症", "腫瘤", "中風", "心臟", "肝炎", "腎臟", "痛風", "骨質疏鬆",
    "關節炎", "皮膚炎", "濕疹", "蕁麻疹", "痘痘", "粉刺", "異位性", "紅疹", "癢",
    "懷孕", "產檢", "產後", "哺乳", "母乳", "嬰兒", "幼兒", "兒童", "寶寶",
    "疫情", "確診", "染疫", "隔離", "快篩", "PCR", "疫苗", "施打", "副作用",
    
    # 藥品相關
    "藥", "藥物", "藥品", "用藥", "吃藥", "藥局", "藥師", "處方", "慢性處方",
    "止痛藥", "消炎藥", "抗生素", "退燒藥", "感冒藥", "胃藥", "止咳", "化痰",
    "維他命", "維生素", "保健食品", "營養品", "益生菌", "魚油", "鈣片", "葉黃素",
    "普拿疼", "斯斯", "伏冒", "克流感", "類固醇", "安眠藥", "降血壓", "降血糖",
    "藥膏", "藥水", "藥粉", "軟膏", "眼藥水", "噴劑", "貼布", "酸痛貼布",
    
    # 健康照護
    "健康", "醫療", "醫院", "診所", "看診", "就醫", "掛號", "急診", "住院",
    "醫生", "醫師", "護理師", "檢查", "體檢", "健檢", "抽血", "X光", "超音波",
    "治療", "復健", "手術", "開刀", "化療", "放療",
    "身體", "健康檢查", "預防", "養生", "保養", "調理", "體質"
]

def is_health_related(text):
    """檢查文章標題或內容是否與健康藥品相關"""
    if not text:
        return False
    text_lower = text.lower()
    return any(keyword in text for keyword in HEALTH_KEYWORDS)

# ==========================================
# 1. PTT 爬蟲
# ==========================================
def crawl_ptt(board="BabyMother", limit_pages=2):
    print(f"[PTT] Start crawling {board}...")
    current_url = f"https://www.ptt.cc/bbs/{board}/index.html"
    articles_list = []
    
    for page in range(limit_pages):
        try:
            resp = requests.get(current_url, headers=HEADERS, cookies=PTT_COOKIES, timeout=10)
            if resp.status_code != 200: break
            
            soup = BeautifulSoup(resp.text, "lxml")
            divs = soup.find_all("div", class_="r-ent")
            
            for div in divs:
                title_div = div.find("div", class_="title")
                if not title_div.a: continue
                title = title_div.a.text.strip()
                link = "https://www.ptt.cc" + title_div.a["href"]
                date_str = div.find("div", class_="date").text.strip()
                
                # 篩選：排除公告，且必須包含健康/藥品關鍵字
                if "公告" in title:
                    continue
                
                if not is_health_related(title):
                    continue
                
                article_data = {
                    "source": "PTT",
                    "board": board,
                    "title": title,
                    "content": title,
                    "url": link,
                    "date": date_str,
                    "crawled_at": datetime.now(),
                    "status": "new"
                }
                db.raw_articles.update_one({"url": link}, {"$set": article_data}, upsert=True)
                articles_list.append(title)

            paging = soup.find("div", class_="btn-group-paging")
            if paging:
                prev_link_tags = paging.find_all("a")
                if len(prev_link_tags) >= 2 and "上頁" in prev_link_tags[1].text:
                    current_url = "https://www.ptt.cc" + prev_link_tags[1]["href"]
                else: break
            time.sleep(random.uniform(0.5, 1.0))
        except Exception as e:
            print(f"[PTT-{board}] Error: {e}")
            break
    print(f"[PTT-{board}] Done, crawled {len(articles_list)} articles.")
    return articles_list

# ==========================================
# 2. Dcard 爬蟲 (Mock 救援模式)
# ==========================================
def crawl_dcard(limit=30):
    # ... (省略真實爬取嘗試，直接回傳 Mock 以確保 Demo 順暢) ...
    # 您可以保留之前的程式碼，這裡為了簡潔直接使用 Mock 邏輯
    print(f"[Dcard] Running crawler (Mock Mode)...")
    MOCK_DCARD_DATA = [
        {"title": "最近流感真的好嚴重，小孩發燒三天了", "board": "parenting", "content": "看了兩次醫生都沒好..."},
        {"title": "請問大家有推薦的維他命C嗎？", "board": "health", "content": "最近辦公室都在感冒..."},
        {"title": "#請益 喉嚨痛到像刀割吃什麼藥有效？", "board": "talk", "content": "已經痛兩天了..."},
        {"title": "藥局看到這個益生菌在特價值得買嗎？", "board": "shopping", "content": "大樹藥局現在買一送一..."},
        {"title": "換季皮膚過敏好癢，求推薦藥膏", "board": "makeup", "content": "臉上紅一塊一塊的..."}
    ]
    
    titles = []
    for mock in MOCK_DCARD_DATA:
        # 檢查是否符合健康關鍵字
        if not is_health_related(mock['title']):
            continue
            
        mock_url = f"https://www.dcard.tw/f/{mock['board']}/p/{random.randint(200000000, 250000000)}"
        article_data = {
            "source": "Dcard",
            "board": mock['board'],
            "title": mock['title'],
            "content": mock['content'],
            "url": mock_url,
            "crawled_at": datetime.now(),
            "status": "mock"
        }
        db.raw_articles.update_one({"title": mock['title']}, {"$set": article_data}, upsert=True)
        titles.append(mock['title'])
        
    print(f"[Dcard] Done, wrote {len(titles)} articles.")
    return titles

# ==========================================
# 3. CDC 疾管署新聞 (新增回來)
# ==========================================
def crawl_cdc():
    print(f"[CDC] Start crawling CDC news...")
    # 這是疾管署的新聞稿列表頁面
    url = "https://www.cdc.gov.tw/Bulletin/List/MmgtpeidAR5Ooai4-fgHzQ"
    
    titles = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")
        
        # 抓取列表中的連結 (class 隨時可能變，目前抓 div.content-boxes-v3 > a)
        # 這裡使用較通用的解法
        links = soup.select(".content-boxes-v3 a")
        
        for link in links[:5]: # 只抓最新的 5 則
            title = link.get("title", "").strip()
            href = link.get("href", "")
            full_url = "https://www.cdc.gov.tw" + href
            
            if not title: continue

            # 判斷風險等級
            risk = "Medium"
            if any(x in title for x in ["死亡", "重症", "流行", "高峰", "緊急"]):
                risk = "High"
            
            alert_data = {
                "agency": "CDC",
                "type": "疫情速訊",
                "title": title,
                "url": full_url,
                "risk_level": risk,
                "crawled_at": datetime.now(),
                "date": datetime.now().strftime("%Y-%m-%d") # 暫用當天日期
            }
            
            # 存入 alerts 集合 (注意：不是 raw_articles)
            db.alerts.update_one({"title": title}, {"$set": alert_data}, upsert=True)
            titles.append(title)
            
        print(f"[CDC] Done, added {len(titles)} alerts.")
        
    except Exception as e:
        print(f"[CDC] Error: {e}")
        
    return titles

# ==========================================
# 4. Google News
# ==========================================
def crawl_google_news(query="流感 OR 腸病毒 OR 缺藥"):
    print(f"[News] Start crawling Google News...")
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    titles = []
    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.content, "xml")
        items = soup.find_all("item")
        for item in items[:10]:
            title = item.title.text
            link = item.link.text
            pub_date = item.pubDate.text
            
            # 篩選健康相關新聞
            if not is_health_related(title):
                continue
            
            article_data = {
                "source": "GoogleNews",
                "board": "News",
                "title": title,
                "content": title,
                "url": link,
                "date": pub_date,
                "crawled_at": datetime.now(),
                "status": "new"
            }
            db.raw_articles.update_one({"url": link}, {"$set": article_data}, upsert=True)
            titles.append(title)
        print(f"[News] Done, added {len(titles)} news.")
    except Exception as e:
        print(f"[News] Error: {e}")
    return titles

# ==========================================
# 主入口
# ==========================================
def run_all_crawlers():
    results = {}
    results["cdc"] = len(crawl_cdc())
    results["dcard"] = len(crawl_dcard())
    results["news"] = len(crawl_google_news())
    
    ptt_count = 0
    for board in PTT_TARGET_BOARDS:
        ptt_count += len(crawl_ptt(board, 1))
    results["ptt"] = ptt_count
    
    return results