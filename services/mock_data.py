"""
MediPoint 全量模拟数据 (中国福建地区)
供前端开发演示使用，无外部 API 依赖。
"""

from datetime import datetime

# ==========================================
# 1. 模拟门店 (福建 3 家)
# ==========================================
STORES = [
    {"store_id": "S001", "name": "福州鼓楼东街店", "city": "福州市", "region": "鼓楼区", "is_demo": True},
    {"store_id": "S002", "name": "厦门思明湖滨店", "city": "厦门市", "region": "思明区", "is_demo": False},
    {"store_id": "S003", "name": "泉州丰泽田安店", "city": "泉州市", "region": "丰泽区", "is_demo": False},
]

# ==========================================
# 2. KPI 摘要
# ==========================================
def kpi_summary():
    return {
        "coverage_label": "热门商品覆盖率",
        "coverage_value": "87%",
        "coverage_trend": "较上周 +3%",
        "coverage_progress": 87,
        "gross_profit": "8,256",
        "margin_rate": "12.4%",
        "margin_status": "low",
        "top_category": "感冒用药 / 中成药",
    }


# ==========================================
# 3. 法规 / 政策警报 (走马灯)
# ==========================================
ALERTS = [
    {"agency": "NMPA", "type": "药品召回", "title": "某批次铝碳酸镁片启动三级召回 (2025-12-15)", "risk_level": "High"},
    {"agency": "福建卫健委", "type": "季节性防控", "title": "冬春季流感与呼吸道传染病防控工作通知", "risk_level": "Medium"},
    {"agency": "福建 CDC", "type": "疫情速讯", "title": "本周流感样病例就诊指数环比上升 18%", "risk_level": "Medium"},
    {"agency": "NMPA", "type": "不良反应", "title": "2025 年第 4 季度药品不良反应监测年度报告发布", "risk_level": "Low"},
    {"agency": "福建 CDC", "type": "疫苗提示", "title": "老年人流感疫苗免费接种工作启动", "risk_level": "Low"},
]


# ==========================================
# 4. 备货 + 促销建议
# ==========================================
SUGGESTIONS = [
    {
        "topic": "流感高峰 — 感冒退烧类",
        "action": "Restock",
        "related_category": "感冒用药 / 退烧",
        "reason": "福建 CDC 通报流感指数环比上升 18%，微博 #流感# 话题阅读量 +220%。",
        "confidence": "A",
        "sources": [
            {"label": "福建 CDC 流感周报", "url": "https://www.fjcdc.com.cn/"},
            {"label": "微博热搜 #全国流感进入高峰#", "url": "https://s.weibo.com/"},
        ],
        "items": [
            {"sku_id": "SKU-FZ-001", "name": "连花清瘟胶囊 (24粒)", "stock": 12, "margin": 32.5, "sales_7d": 28, "status": "Critical"},
            {"sku_id": "SKU-FZ-002", "name": "布洛芬缓释胶囊 (20粒)", "stock": 18, "margin": 28.0, "sales_7d": 22, "status": "Critical"},
        ],
        "talking_points": "近期流感活动明显上升，建议提前 1-2 天服用连花清瘟，可搭配布洛芬用于退烧。",
    },
    {
        "topic": "换季过敏 — 鼻喷 / 抗组胺",
        "action": "Restock",
        "related_category": "过敏 / 鼻喷",
        "reason": "小红书「换季过敏」笔记数 +85%，厦门地区花粉指数偏高。",
        "confidence": "B",
        "sources": [
            {"label": "小红书 #换季过敏# 话题", "url": "https://www.xiaohongshu.com/"},
        ],
        "items": [
            {"sku_id": "SKU-FZ-010", "name": "氯雷他定片 (12片)", "stock": 24, "margin": 30.0, "sales_7d": 12, "status": "Warning"},
        ],
        "talking_points": "换季鼻痒、打喷嚏多为过敏性鼻炎，可先尝试氯雷他定 1 片/日。",
    },
    {
        "topic": "清热解暑 — 藿香正气",
        "action": "Restock",
        "related_category": "中成药 / 肠胃",
        "reason": "南方湿热天气持续，藿香正气类搜索量显著上升。",
        "confidence": "B",
        "sources": [
            {"label": "微博 #南方湿热# 话题", "url": "https://s.weibo.com/"},
        ],
        "items": [
            {"sku_id": "SKU-FZ-021", "name": "藿香正气水 (10支)", "stock": 22, "margin": 26.0, "sales_7d": 14, "status": "Warning"},
        ],
        "talking_points": "暑湿感冒伴肠胃不适可推荐藿香正气水；驾驶员请改用无醇剂型。",
    },
    {
        "topic": "库存积压 — 维 C 泡腾片",
        "action": "Promotion",
        "related_category": "维生素 / 营养",
        "reason": "本店该 SKU 库存 230 盒，远超安全水位 (50)，需要清库。",
        "confidence": "A",
        "sources": [{"label": "内部 ERP 库存报表", "url": "#"}],
        "items": [
            {"sku_id": "SKU-FZ-100", "name": "维 C 泡腾片 (20片装)", "stock": 230, "margin": 45.0, "sales_7d": 4, "status": "Overstock"},
        ],
        "talking_points": "可搭配感冒类商品做「防护组合」促销，店员主动推荐提升客单价。",
    },
    {
        "topic": "库存积压 — 咽喉含片",
        "action": "Promotion",
        "related_category": "咽喉 / 含片",
        "reason": "库存 180 盒远超安全水位，建议捆绑销售或搭赠清库。",
        "confidence": "C",
        "sources": [{"label": "内部 ERP 库存报表", "url": "#"}],
        "items": [
            {"sku_id": "SKU-FZ-101", "name": "复方草珊瑚含片 (16片)", "stock": 180, "margin": 38.0, "sales_7d": 6, "status": "Overstock"},
        ],
        "talking_points": "教师 / 销售 / 直播主播可推荐复方草珊瑚含片缓解咽喉不适。",
    },
]


# ==========================================
# 5. 全网舆情 (微博 / 小红书 / 政府公告)
# ==========================================
SENTIMENT = {
    "Weibo": [
        {"title": "#全国流感进入高峰# 多地儿科门诊爆满", "content": "国家流感中心通报本周南方省份流感阳性率 32.4%，建议家中常备退烧药。", "tags": ["流感", "儿科", "退烧"], "sentiment": "concern", "url": "https://s.weibo.com/"},
        {"title": "#连花清瘟断货# 福州多家药店补货", "content": "网友晒图反映福州部分门店连花清瘟售罄，店员称 2 日内到货。", "tags": ["连花清瘟", "缺货", "补货"], "sentiment": "neutral", "url": "https://s.weibo.com/"},
        {"title": "#湿热天气养生# 藿香正气搜索量上涨 70%", "content": "微博健康 KOL 建议湿热节气家中常备藿香正气类中成药。", "tags": ["湿热", "养生", "中成药"], "sentiment": "positive", "url": "https://s.weibo.com/"},
        {"title": "#儿童退烧药怎么选# 家长热议", "content": "布洛芬 vs 对乙酰氨基酚对比，药师在线答疑。", "tags": ["儿童", "退烧", "布洛芬"], "sentiment": "concern", "url": "https://s.weibo.com/"},
        {"title": "#NMPA 新药获批# 国产降糖药 SGLT2 抑制剂上市", "content": "国家药监局批准国产创新降糖药，可改善心衰预后。", "tags": ["NMPA", "新药", "降糖"], "sentiment": "positive", "url": "https://s.weibo.com/"},
        {"title": "#厦门花粉浓度# 思明区达中等偏高", "content": "过敏体质人群外出建议佩戴口罩，可备氯雷他定。", "tags": ["厦门", "花粉", "过敏"], "sentiment": "neutral", "url": "https://s.weibo.com/"},
        {"title": "#慢性病用药# 冬季血压波动提醒", "content": "心内科医生提醒冬季高血压患者需监测血压，调整用药。", "tags": ["慢性病", "高血压", "冬季"], "sentiment": "neutral", "url": "https://s.weibo.com/"},
        {"title": "#NMPA 通报# 某批次胃药召回", "content": "国家药监局通报某批次铝碳酸镁片因溶出度不合格启动三级召回。", "tags": ["NMPA", "召回", "胃药"], "sentiment": "negative", "url": "https://s.weibo.com/"},
    ],
    "Xiaohongshu": [
        {"title": "家庭常备药箱清单 (2025 冬季版)", "content": "退烧、感冒、肠胃、外伤四大类必备，附购买渠道。", "tags": ["常备药", "清单", "家庭"], "sentiment": "positive", "url": "https://www.xiaohongshu.com/"},
        {"title": "宝宝发烧 38.5℃ 在家怎么处理", "content": "物理降温 + 退烧药使用经验分享，3 天退烧记录。", "tags": ["宝宝", "退烧", "经验"], "sentiment": "positive", "url": "https://www.xiaohongshu.com/"},
        {"title": "换季过敏性鼻炎自救指南", "content": "氯雷他定 + 鼻喷 + 空气净化器三件套。", "tags": ["过敏", "鼻炎", "自救"], "sentiment": "positive", "url": "https://www.xiaohongshu.com/"},
        {"title": "维 C 真的是越贵越好吗", "content": "药店药师拆解泡腾片 vs 咀嚼片 vs 软糖。", "tags": ["维C", "测评", "营养"], "sentiment": "neutral", "url": "https://www.xiaohongshu.com/"},
        {"title": "孕妇感冒能不能吃药", "content": "妇产科医生建议：对乙酰氨基酚为孕期相对安全选项。", "tags": ["孕妇", "感冒", "安全用药"], "sentiment": "neutral", "url": "https://www.xiaohongshu.com/"},
        {"title": "药店店员不会告诉你的 5 个秘密", "content": "联合用药 / 毛利 / 推荐机制内幕。", "tags": ["药店", "内幕", "联合用药"], "sentiment": "neutral", "url": "https://www.xiaohongshu.com/"},
        {"title": "胃药饭前吃还是饭后吃", "content": "PPI / 铝碳酸镁 / 莫沙必利服用时间图解。", "tags": ["胃药", "服用时间", "图解"], "sentiment": "positive", "url": "https://www.xiaohongshu.com/"},
        {"title": "雾化在家做可行吗", "content": "医生建议儿童雾化需医师处方，不建议家长自行操作。", "tags": ["雾化", "儿童", "处方"], "sentiment": "neutral", "url": "https://www.xiaohongshu.com/"},
    ],
    "GovNotice": [
        {"title": "福建省卫健委关于做好冬春季流感防控工作的通知", "content": "要求各级医疗机构、药店加强抗病毒药与防护物资储备。", "tags": ["福建", "流感", "政策"], "sentiment": "neutral", "url": "http://wjw.fujian.gov.cn/"},
        {"title": "福建 CDC 流感周报：本周 ILI% 上升至 8.4%", "content": "流感样病例就诊比例明显上升，以 A(H3N2) 为主。", "tags": ["福建", "CDC", "流感周报"], "sentiment": "concern", "url": "http://www.fjcdc.com.cn/"},
        {"title": "NMPA 关于发布 2025 年药品上市许可持有人年度报告的公告", "content": "强调持有人主体责任，要求强化药品全生命周期管理。", "tags": ["NMPA", "MAH", "年度报告"], "sentiment": "neutral", "url": "https://www.nmpa.gov.cn/"},
        {"title": "NMPA 通报：某批次铝碳酸镁片三级召回", "content": "涉事批次溶出度不合格，要求各省级局监督召回。", "tags": ["NMPA", "召回", "胃药"], "sentiment": "negative", "url": "https://www.nmpa.gov.cn/"},
        {"title": "福建 CDC 老年人流感疫苗免费接种通知", "content": "福州、厦门、泉州三地 65 岁以上老人可到社区免费接种。", "tags": ["福建", "疫苗", "老人"], "sentiment": "positive", "url": "http://www.fjcdc.com.cn/"},
    ],
}


# ==========================================
# 6. 法规 / 政策通告
# ==========================================
REGULATIONS = [
    {
        "source": "NMPA",
        "title": "关于发布 2025 年第 4 季度药品不良反应监测年度报告的公告",
        "summary": "本年度共收到不良反应报告 215.3 万份，同比增长 6.2%。抗感染药报告占比仍居首位。",
        "affected_categories": ["抗感染药", "中药注射剂"],
        "risk_level": "Medium",
        "published_at": "2025-12-20",
        "response": "门店需对高频投诉品种进行重点登记，配合药师问诊。",
    },
    {
        "source": "NMPA",
        "title": "关于某批次铝碳酸镁片启动三级召回的公告",
        "summary": "涉事生产企业某批次溶出度不符合标准，可能影响疗效。",
        "affected_categories": ["胃药", "消化系统"],
        "risk_level": "High",
        "published_at": "2025-12-15",
        "response": "立即下架相关批次，留存进货单据，等待厂家召回通知。",
    },
    {
        "source": "福建卫健委",
        "title": "关于做好冬春季流感与呼吸道传染病防控工作的通知",
        "summary": "要求加强药品储备，药店、基层医疗机构 24 小时保障退烧止咳药品供应。",
        "affected_categories": ["退烧药", "止咳药", "感冒药"],
        "risk_level": "High",
        "published_at": "2025-12-10",
        "response": "门店需对连花清瘟、布洛芬、止咳糖浆等核心 SKU 维持 14 天安全库存。",
    },
    {
        "source": "福建卫健委",
        "title": "关于推进电子处方流转工作的实施意见",
        "summary": "鼓励互联网医院处方流转至零售药店，凭电子处方销售处方药。",
        "affected_categories": ["处方药", "互联网医疗"],
        "risk_level": "Low",
        "published_at": "2025-11-28",
        "response": "门店可对接合规电子处方平台，扩大处方药销售半径。",
    },
    {
        "source": "福建 CDC",
        "title": "2025 年第 50 周流感周报",
        "summary": "南方省份流感阳性率 32.4%，ILI% 8.4%，以 A(H3N2) 型为主。",
        "affected_categories": ["抗病毒药", "退烧药"],
        "risk_level": "Medium",
        "published_at": "2025-12-16",
        "response": "门店可增加奥司他韦、布洛芬、连花清瘟陈列与库存。",
    },
    {
        "source": "福建 CDC",
        "title": "老年人流感疫苗免费接种工作启动通知",
        "summary": "福州、厦门、泉州三地 65 岁以上老人可到社区免费接种四价流感疫苗。",
        "affected_categories": ["疫苗", "公共卫生"],
        "risk_level": "Low",
        "published_at": "2025-10-08",
        "response": "门店可张贴海报协助宣传，引导老人前往就近社区接种。",
    },
    {
        "source": "福建 CDC",
        "title": "手足口病疫情风险提示 (12 月)",
        "summary": "12 月为手足口病低发期，但 EV71 仍可在托幼机构散发，提示做好晨检。",
        "affected_categories": ["儿科", "抗病毒药"],
        "risk_level": "Low",
        "published_at": "2025-12-05",
        "response": "门店维持口腔炎喷雾、利巴韦林等儿科 SKU 正常库存即可。",
    },
]


# ==========================================
# 7. AI 药师助手 FAQ
# 顺序很重要: 「药品名 + 主题」组合的条目在前, 通用主题条目在后,
# 否则 "连花清瘟怎么吃" 会先命中通用「怎么吃」而错过连花清瘟专答。
# ==========================================
CHAT_FAQ = [
    {
        "patterns": ["连花清瘟"],
        "answer": "连花清瘟用于轻症流感 / 感冒，不预防新冠。服用期间忌烟酒辛辣，与滋补性中药间隔 2 小时。",
        "source": "国家中医药管理局《中医药治疗流感临床实践指南》",
    },
    {
        "patterns": ["布洛芬", "美林"],
        "answer": "布洛芬成人 200-400 mg / 次，每 4-6 小时一次。儿童使用美林混悬液，按体重 5-10 mg/kg。",
        "source": "国家药品说明书 / WHO 基本药物清单",
    },
    {
        "patterns": ["藿香正气", "湿热", "中暑"],
        "answer": "藿香正气水含乙醇，驾驶员 / 儿童建议改用不含醇的藿香正气胶囊 / 滴丸剂型。",
        "source": "国家药监局 OTC 说明",
    },
    {
        "patterns": ["维C", "维生素C", "泡腾片"],
        "answer": "成人每日维 C 推荐摄入量 100 mg，泡腾片 1 片即可。胃溃疡患者不建议长期高剂量服用。",
        "source": "中国营养学会 DRIs 2023",
    },
    {
        "patterns": ["胃药", "胃痛", "胃酸", "反酸"],
        "answer": "反酸烧心可使用铝碳酸镁 (达喜) 餐后 1 小时嚼服；PPI 类 (奥美拉唑) 需空腹服用，疗程不超过 8 周。",
        "source": "《中国胃食管反流病诊治指南》",
    },
    {
        "patterns": ["高血压", "降压"],
        "answer": "冬季血压易波动，建议早晚各测一次。常用降压药 (沙坦类 / 地平类) 需每日固定时间服用，不可擅自停药。",
        "source": "《中国高血压防治指南》2024",
    },
    {
        "patterns": ["糖尿病", "降糖"],
        "answer": "口服降糖药种类多 (二甲双胍 / SGLT2 抑制剂 / DPP-4 抑制剂)，需根据肾功能、体重综合评估，请遵医嘱。",
        "source": "《中国 2 型糖尿病防治指南》2024",
    },
    {
        "patterns": ["头孢", "抗生素", "消炎药"],
        "answer": "抗生素仅针对细菌感染，病毒性感冒 (如普通感冒 / 流感) 无效。务必凭处方销售，避免滥用。",
        "source": "国家卫健委《抗菌药物临床应用管理办法》",
    },
    {
        "patterns": ["失眠", "睡不着", "安眠"],
        "answer": "短期失眠可尝试褪黑素 + 改善睡眠卫生 (固定作息、避免咖啡因)。长期失眠 (>1 月) 建议就医评估。",
        "source": "《中国成人失眠诊断和治疗指南》",
    },
    {
        "patterns": ["咳嗽", "止咳", "喉咙痛"],
        "answer": "干咳可用右美沙芬糖浆；痰多咳嗽建议先化痰 (氨溴索) 再止咳。含片 (草珊瑚 / 西瓜霜) 适合轻度咽痛。",
        "source": "《咳嗽基层诊疗指南》",
    },
    {
        "patterns": ["过敏", "鼻炎", "打喷嚏", "鼻痒"],
        "answer": "过敏性鼻炎一线用药为口服抗组胺药 (氯雷他定 / 西替利嗪)，可联合鼻用糖皮质激素喷雾。",
        "source": "《变应性鼻炎诊断和治疗指南》2022",
    },
    {
        "patterns": ["替代", "替代品", "有别的吗", "换一种"],
        "answer": "退烧药：布洛芬 ↔ 对乙酰氨基酚可互换。感冒中成药：连花清瘟 ↔ 抗病毒口服液 / 板蓝根。建议根据症状选择。",
        "source": "MediPoint RAG 知识库 v2.1",
    },
    {
        "patterns": ["怎么吃", "怎么服用", "服用方法", "用法用量"],
        "answer": "请先阅读药品说明书。一般退烧药每 4-6 小时可重复给药一次，24 小时内不超过 4 次。儿童需按体重计算剂量。",
        "source": "《中国非处方药用药指南》第 3 章",
    },
    {
        "patterns": ["孕妇", "怀孕", "孕期"],
        "answer": "孕期感冒退烧优先选择对乙酰氨基酚 (必理通)，布洛芬在孕晚期禁用。任何用药前请先咨询产检医生。",
        "source": "FDA 妊娠期用药分级 B / D",
    },
    {
        "patterns": ["小孩", "儿童", "宝宝", "婴儿", "幼儿"],
        "answer": "3 月以下婴儿发热请立即就医。儿童退烧首选对乙酰氨基酚混悬液，按体重 10-15 mg/kg 给药。",
        "source": "WHO 儿童退烧用药指南",
    },
]


# ==========================================
# 聚合函数
# ==========================================
def dashboard_payload():
    return {
        "report_date": datetime.now().strftime("%Y-%m-%d"),
        "kpiData": kpi_summary(),
        "alerts": ALERTS,
        "suggestions": SUGGESTIONS,
        "insights": SENTIMENT["Weibo"][:5] + SENTIMENT["Xiaohongshu"][:3] + SENTIMENT["GovNotice"][:2],
    }


def sentiment_payload():
    flat = []
    for source, items in SENTIMENT.items():
        for it in items:
            flat.append({**it, "source": source, "crawled_at": datetime.now().isoformat()})
    return {
        "items": flat,
        "keyword_trend": [
            {"keyword": "流感", "value": 92},
            {"keyword": "连花清瘟", "value": 78},
            {"keyword": "布洛芬", "value": 65},
            {"keyword": "过敏", "value": 54},
            {"keyword": "湿热", "value": 47},
            {"keyword": "高血压", "value": 41},
            {"keyword": "维C", "value": 35},
        ],
        "seven_day_series": [
            {"date": "12-09", "Weibo": 22, "Xiaohongshu": 18, "GovNotice": 3},
            {"date": "12-10", "Weibo": 28, "Xiaohongshu": 21, "GovNotice": 4},
            {"date": "12-11", "Weibo": 31, "Xiaohongshu": 24, "GovNotice": 2},
            {"date": "12-12", "Weibo": 35, "Xiaohongshu": 27, "GovNotice": 3},
            {"date": "12-13", "Weibo": 41, "Xiaohongshu": 30, "GovNotice": 5},
            {"date": "12-14", "Weibo": 48, "Xiaohongshu": 33, "GovNotice": 4},
            {"date": "12-15", "Weibo": 56, "Xiaohongshu": 36, "GovNotice": 6},
        ],
    }


def decisions_payload():
    return {
        "stores": STORES,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "restock": [s for s in SUGGESTIONS if s["action"] == "Restock"],
        "promotion": [s for s in SUGGESTIONS if s["action"] == "Promotion"],
    }


def regulations_payload():
    return {"items": REGULATIONS}


def chat_reply(message: str) -> dict:
    """基于关键词的简单 FAQ 匹配"""
    msg = (message or "").strip()
    if not msg:
        return {"answer": "请输入您想咨询的用药问题。", "source": "MediPoint RAG", "confidence": "low"}

    for faq in CHAT_FAQ:
        if any(p in msg for p in faq["patterns"]):
            return {"answer": faq["answer"], "source": faq["source"], "confidence": "high"}

    return {
        "answer": "您的问题比较具体，建议咨询门店执业药师或前往医院就诊。我已为您记录，可在 MediPoint 终端发起视频问诊。",
        "source": "MediPoint AI 默认兜底",
        "confidence": "low",
    }
