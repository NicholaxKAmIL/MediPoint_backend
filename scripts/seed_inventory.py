"""
一次性 seed 脚本 — 给 S001 / S002 / S003 三家店各灌入 8+ 个示例库存,
覆盖低库存 (触发 Restock) + 高库存 (触发 Promotion) + 正常水位
用法: python scripts/seed_inventory.py
"""
import sys
sys.path.insert(0, '.')
from datetime import datetime, timedelta
from db.mongo import db

SAMPLE = {
    "S001": [
        ("SKU-FZ-001", "连花清瘟胶囊 (24粒)",  "感冒/退烧",  12, 32.5, 28),
        ("SKU-FZ-002", "布洛芬缓释胶囊 (20粒)", "止痛/退烧",  8,  28.0, 22),
        ("SKU-FZ-003", "藿香正气水 (10支)",     "中成药/肠胃", 18, 26.0, 14),
        ("SKU-FZ-004", "感冒灵颗粒 (10袋)",     "感冒/退烧",  6,  29.0, 19),
        ("SKU-FZ-005", "板蓝根颗粒 (10袋)",     "中成药/清热", 14, 27.0, 11),
        ("SKU-FZ-006", "氯雷他定片 (12片)",     "过敏/鼻喷",  11, 30.0, 16),
        ("SKU-FZ-007", "对乙酰氨基酚片 (20片)",  "止痛/退烧",  9,  27.5, 20),
        ("SKU-FZ-008", "急支糖浆 (100ml)",      "咳嗽/止咳",  15, 30.0, 13),
        ("SKU-FZ-100", "维 C 泡腾片 (20片装)",   "维生素/营养", 230, 45.0, 4),
        ("SKU-FZ-101", "复方草珊瑚含片 (16片)",  "咽喉/含片",   180, 38.0, 6),
        ("SKU-FZ-102", "钙尔奇 D 片 (60片)",    "钙片/营养",   145, 36.0, 5),
    ],
    "S002": [
        ("SKU-XM-001", "糠酸莫米松鼻喷雾剂 (60喷)", "过敏/鼻喷",  9,  34.0, 25),
        ("SKU-XM-002", "氯雷他定片 (12片)",       "过敏/鼻喷",  14, 30.0, 19),
        ("SKU-XM-003", "对乙酰氨基酚片 (20片)",   "止痛/退烧",  21, 27.5, 16),
        ("SKU-XM-004", "连花清瘟胶囊 (24粒)",     "感冒/退烧",  7,  32.5, 30),
        ("SKU-XM-005", "藿香正气水 (10支)",       "中成药/肠胃", 13, 26.0, 12),
        ("SKU-XM-006", "布洛芬缓释胶囊 (20粒)",   "止痛/退烧",  10, 28.0, 18),
        ("SKU-XM-007", "板蓝根颗粒 (10袋)",       "中成药/清热", 16, 27.0, 9),
        ("SKU-XM-008", "小儿氨酚黄那敏颗粒 (6袋)", "儿科/感冒",  5,  31.0, 22),
        ("SKU-XM-100", "乳清蛋白粉礼盒 (1kg)",    "蛋白/营养", 165, 42.0, 5),
        ("SKU-XM-101", "维 C 泡腾片 (20片装)",    "维生素/营养", 140, 45.0, 3),
    ],
    "S003": [
        ("SKU-QZ-001", "藿香正气水 (10支)",      "中成药/肠胃", 10, 26.0, 26),
        ("SKU-QZ-002", "保和丸 (200丸)",         "中成药/肠胃", 16, 28.5, 18),
        ("SKU-QZ-003", "布洛芬缓释胶囊 (20粒)",   "止痛/退烧",   20, 28.0, 17),
        ("SKU-QZ-004", "连花清瘟胶囊 (24粒)",     "感冒/退烧",   11, 32.5, 24),
        ("SKU-QZ-005", "急支糖浆 (100ml)",       "咳嗽/止咳",   13, 30.0, 15),
        ("SKU-QZ-006", "板蓝根颗粒 (10袋)",       "中成药/清热", 17, 27.0, 11),
        ("SKU-QZ-007", "对乙酰氨基酚片 (20片)",   "止痛/退烧",   8,  27.5, 21),
        ("SKU-QZ-008", "复方草珊瑚含片 (16片)",   "咽喉/含片",   22, 38.0, 9),
        ("SKU-QZ-100", "板蓝根颗粒 (10袋) 大包装", "中成药/清热", 210, 40.0, 6),
        ("SKU-QZ-101", "邦迪创可贴大盒 (100片)",  "外用/创可贴", 140, 36.0, 4),
    ],
}


def main():
    yesterday = (datetime.utcnow() - timedelta(hours=12)).strftime("%Y-%m-%d")
    inserted = 0
    for store, items in SAMPLE.items():
        for sku_id, sku_name, cat, stock, margin, sales_7d in items:
            db.inventory.update_one(
                {"store_id": store, "sku_id": sku_id},
                {"$set": {
                    "store_id": store,
                    "sku_id": sku_id,
                    "sku_name": sku_name,
                    "category": cat,
                    "closing_on_hand": stock,
                    "margin": margin,
                    "sales_7d": sales_7d,
                    "date": yesterday,
                }},
                upsert=True,
            )
            inserted += 1
    print(f"seeded {inserted} inventory records for date {yesterday} "
          f"({', '.join(f'{sid}={len(items)}' for sid, items in SAMPLE.items())})")


if __name__ == "__main__":
    main()
