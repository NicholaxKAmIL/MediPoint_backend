"""
FJ CDC 静态兜底数据 (dev 环境 TLS 握手失败时使用)
格式与 db.alerts 一致, published_at 为近期日期。
"""
from datetime import datetime, timedelta

_NOW = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)


def _days_ago(n: int) -> datetime:
    return _NOW - timedelta(days=n)


STATIC_FJCDC_ALERTS: list[dict] = [
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "流感周报",
        "type": "疫情速讯",
        "title": "福建省 2025 年第 50 周流感监测周报",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&weekly=2025W50",
        "summary": "本周流感样病例 (ILI%) 就诊比例为 8.4%，较上周上升 1.2 个百分点。检测阳性以 A(H3N2) 亚型为主，南平、三明报告数偏高。",
        "risk_level": "Medium",
        "published_at": _days_ago(5),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["抗病毒药", "退烧药"],
    },
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "疫情速讯",
        "type": "风险提示",
        "title": "诺如病毒感染性腹泻进入冬季高发期",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&topic=2025winter-noro",
        "summary": "近 4 周全省报告诺如病毒急性胃肠炎聚集性疫情 7 起，主要发生在学校和养老机构。建议加强手卫生与餐饮具消毒。",
        "risk_level": "Medium",
        "published_at": _days_ago(12),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["肠道用药", "口服补液盐"],
    },
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "疫苗提示",
        "type": "公共卫生",
        "title": "老年人流感疫苗免费接种工作全面启动",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&topic=2025-flu-vaccine-elderly",
        "summary": "福州、厦门、泉州、三明、南平五地 65 岁以上常住老人可凭身份证到就近社区卫生服务中心免费接种四价流感疫苗。",
        "risk_level": "Low",
        "published_at": _days_ago(20),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["疫苗", "公共卫生"],
    },
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "疫情速讯",
        "type": "风险提示",
        "title": "手足口病疫情 12 月风险提示",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&topic=2025-dec-hfmd",
        "summary": "12 月为手足口病低发期，但 EV71 病毒仍可在托幼机构散发，提示托幼机构做好晨检与玩具消毒。",
        "risk_level": "Low",
        "published_at": _days_ago(28),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["儿科", "抗病毒药"],
    },
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "监测报告",
        "type": "公共卫生",
        "title": "福建省 2025 年 11 月突发公共卫生事件月报",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&month=2025-11",
        "summary": "11 月共报告突发公共卫生事件 4 起 (流感 2 起、水痘 1 起、诺如 1 起)，均已规范处置，无死亡病例。",
        "risk_level": "Low",
        "published_at": _days_ago(35),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["公共卫生", "疾控"],
    },
    {
        "source": "FJ_CDC",
        "agency": "福建 CDC",
        "category": "疫情公告",
        "type": "死亡病例",
        "title": "厦门市报告 1 例人感染 H5N6 禽流感重症病例",
        "url": "https://www.fjcdc.com.cn/jkjy_list?ctlgid=644621&case=h5n6-2025",
        "summary": "患者有活禽市场暴露史，已隔离治疗，密切接触者医学观察中。提示零售药店重点关注抗病毒药 (奥司他韦) 库存。",
        "risk_level": "High",
        "published_at": _days_ago(45),
        "crawled_at": _NOW,
        "crawled_via": "static_fallback",
        "affected_categories": ["抗病毒药", "重症救治"],
    },
]
