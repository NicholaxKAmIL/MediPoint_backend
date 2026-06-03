"""
实体词典 — 药品 / 疾病 / 症状 / 品牌
用于 sentiment API 的轻量本地实体抽取 (零 LLM 调用)。
- 数据来自 services/data_drug_monographs.py + 行业常识, 全部中文
- 词典去重按字符串长度倒序匹配, 避免 "布洛芬" 被 "布" 截走
"""
from __future__ import annotations

DRUGS: list[str] = [
    "连花清瘟胶囊", "连花清瘟", "布洛芬缓释胶囊", "布洛芬", "布洛芬混悬液", "美林",
    "对乙酰氨基酚", "氨酚黄那敏", "小儿氨酚黄那敏颗粒", "藿香正气水", "藿香正气",
    "板蓝根颗粒", "板蓝根", "感冒灵", "急支糖浆", "复方草珊瑚含片", "草珊瑚含片",
    "氯雷他定", "氯雷他定片", "糠酸莫米松鼻喷雾剂", "糠酸莫米松", "铝碳酸镁", "铝碳酸镁片",
    "保和丸", "右美沙芬", "尿素维 E 乳膏", "维 C 泡腾片", "维生素 C",
    "钙尔奇 D", "钙尔奇", "乳清蛋白粉", "蛋白粉", "眠安宁颗粒", "二丁胶囊",
    "复方鱼腥草合剂", "蒲地蓝消炎口服液", "蒲地蓝", "恒格列净", "奥司他韦",
]

DISEASES: list[str] = [
    "流感", "流行性感冒", "感冒", "新冠", "新型冠状病毒", "诺如", "诺如病毒",
    "手足口", "手足口病", "麻疹", "风疹", "腮腺炎", "流行性腮腺炎",
    "肺结核", "结核", "肝炎", "病毒性肝炎", "艾滋病", "HIV",
    "高血压", "糖尿病", "冠心病", "心衰", "心绞痛", "心肌梗死",
    "过敏性鼻炎", "鼻炎", "哮喘", "湿疹", "皮炎", "过敏",
    "腹泻", "感染性腹泻", "便秘", "消化不良", "胃炎", "胃溃疡",
    "登革热", "疟疾", "狂犬病", "猴痘", "基孔肯雅热", "炭疽", "白喉",
    "发热伴血小板减少综合征", "呼吸道感染", "急性出血性结膜炎", "结膜炎",
]

SYMPTOMS: list[str] = [
    "发热", "发烧", "高烧", "低烧", "咳嗽", "干咳", "痰咳", "咽痛", "咽喉肿痛",
    "鼻塞", "流涕", "打喷嚏", "头痛", "肌肉酸痛", "关节痛", "乏力", "胸闷",
    "气短", "心悸", "腹痛", "腹泻", "呕吐", "恶心", "腹胀", "食欲不振",
    "皮疹", "瘙痒", "红肿", "过敏", "鼻痒", "流泪", "皮肤干燥", "皲裂",
    "失眠", "多梦", "心悸不宁", "血压波动", "血糖升高",
]

BRANDS: list[str] = [
    "美林", "芬必得", "泰诺", "泰诺林", "999", "感冒灵", "板蓝根", "白云山",
    "同仁堂", "云南白药", "哈药六厂", "江中", "修正", "葵花", "三九", "999 感冒灵",
    "钙尔奇", "汤臣倍健", "善存", "安利", "Swisse", "养生堂", "康恩贝", "邦迪",
]

ALL: list[str] = DRUGS + DISEASES + SYMPTOMS + BRANDS
CATEGORIES: dict[str, list[str]] = {
    "drugs": DRUGS,
    "diseases": DISEASES,
    "symptoms": SYMPTOMS,
    "brands": BRANDS,
}


def extract(text: str) -> dict[str, list[str]]:
    """从文本中抽取 4 类实体, 去重保序, 命中后从原文中标记掉以避免子串误判。"""
    if not text:
        return {"drugs": [], "diseases": [], "symptoms": [], "brands": []}

    result: dict[str, set[str]] = {k: set() for k in CATEGORIES}
    masked = text
    sorted_all = sorted(ALL, key=lambda x: -len(x))
    for kw in sorted_all:
        if kw and kw in masked:
            for cat, words in CATEGORIES.items():
                if kw in words:
                    result[cat].add(kw)
                    masked = masked.replace(kw, " " * len(kw))
                    break

    return {k: sorted(v) for k, v in result.items()}
