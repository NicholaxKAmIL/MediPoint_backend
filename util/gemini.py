import json
from typing import Dict, Any, List
from openai import OpenAI
from util.config import env


if not env.DEEPSEEK_API_KEY:
    pass
else:
    client = OpenAI(
        api_key=env.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com"
    )

MODEL_NAME = "deepseek-chat"

def generate_talking_point(topic: str, products: List[str], reason: str) -> str:
    """
    專為 Dashboard 生成「藥師銷售話術」。
    topic: 議題 (ex: 流感高峰)
    products: 相關藥品名稱列表
    reason: 系統判斷的原因 (ex: 庫存告急)
    """
    try:
        prompt = f"""
        你是一位資深藥局店長。
        情況：{topic}
        相關商品：{', '.join(products)}
        系統偵測原因：{reason}

        請生成一句「簡短、專業且具備商業說服力」的備貨或銷售建議話術給藥師看。
        限制：30字以內，繁體中文。
        """
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=100,
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return "建議依照過往銷量與目前庫存水位進行彈性調整。"