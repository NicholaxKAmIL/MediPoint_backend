"""
LLM 工具 (DeepSeek OpenAI 兼容客户端)
- generate_talking_point: 同步, 用于决策建议话术
- stream_chat_pharmacist: 异步生成器, 用于 SSE 流式对话
- 失败/无 key 时降级为 FAQ 关键词匹配
"""
from __future__ import annotations
import logging
from typing import AsyncIterator

from openai import AsyncOpenAI, OpenAI

from util.config import env

log = logging.getLogger(__name__)

MODEL_NAME = "deepseek-chat"

_sync_client: OpenAI | None = None
_async_client: AsyncOpenAI | None = None
if env.DEEPSEEK_API_KEY:
    _sync_client = OpenAI(
        api_key=env.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )
    _async_client = AsyncOpenAI(
        api_key=env.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )

SYSTEM_PROMPT = """你是一位资深执业药师，服务于福建省零售药店。回答用户的用药/剂量/替代品/合规问题。
- 严格基于《中国药典》《国家基本药物目录》《NMPA 公告》及福建省级文件
- 简明扼要 (50-150 字)，列点回答
- 涉及处方药时建议咨询医师
- 不确定时明确告知"""


def generate_talking_point(topic: str, products: list[str], reason: str) -> str:
    """同步: 生成药师行销/销售话术 (非备货指令)。
    无 key / 失败时返回模板。
    """
    if not _sync_client:
        return _fallback_talking_point(products)
    try:
        prompt = (
            f"你是一位资深执业药师，正在为到店顾客做专业推荐。\n"
            f"当前情境：{topic}\n"
            f"涉及商品：{', '.join(products)}\n"
            f"背景：{reason}\n\n"
            f"请生成一句「药师对顾客说的行销/销售话术」（不是备货指令）。\n"
            f"要求：\n"
            f"1. 站在药师面对顾客的角度，给出推销、推荐搭配、关联销售或促销引导的话术\n"
            f"2. 不要写「建议立即补货」「通知采购」这类内部备货指令\n"
            f"3. 如有相关公告/疫情，可作为推荐理由融入话术\n"
            f"4. 限制：30-60 字，简体中文，专业有说服力\n"
            f"5. 只输出话术本身，不要加任何前缀或解释"
        )
        resp = _sync_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("generate_talking_point LLM call failed: %s", e)
        return _fallback_talking_point(products)


# 用结构化分隔符让 LLM 一次返回 话术 + 搭配, 解析失败时各字段独立兜底
_MARKETING_PAIR_DELIM = "【搭配】"


def _fallback_upsell(products: list[str]) -> str:
    if not products:
        return "建议搭配店内同类热销品。"
    if len(products) >= 2:
        return f"建议搭配：{products[0]} + {products[1]}"
    return f"建议搭配：{products[0]} 同款家庭装"


def generate_marketing_pair(topic: str, products: list[str], reason: str) -> dict:
    """同步: 一次 LLM 调用同时生成话术 + 搭配推荐 (保证两者产品一致)。
    无 key / 失败时返回 {talking_point, upsell} (含兜底模板)。
    """
    fallback_talk = _fallback_talking_point(products)
    fallback_upsell = _fallback_upsell(products)
    if not _sync_client:
        return {"talking_point": fallback_talk, "upsell": fallback_upsell}

    try:
        prompt = (
            f"你是一位资深执业药师，正在为到店顾客做专业推荐。\n"
            f"当前情境：{topic}\n"
            f"涉及商品（店内有售）：{', '.join(products)}\n"
            f"背景：{reason}\n\n"
            f"请按以下格式严格输出两行, 中间用换行分隔, 不要加任何其他内容:\n"
            f"第一行【话术】: 一句药师对顾客说的行销/销售话术 (30-60字, 简体中文, 不要写「建议立即补货」这类内部备货指令)\n"
            f"第二行【搭配】: 「建议搭配：」+ 1-2 个「店内有售商品」清单中的关联商品 (必须与第一行话术提到的是同一治疗方向, 例如话术提到藿香正气, 搭配也必须是藿香正气类或同类中成药, 不能跳到维生素C或其他无关品类)\n\n"
            f"严格要求:\n"
            f"- 搭配商品必须从「店内有售商品」清单中选取, 不可虚构\n"
            f"- 搭配商品必须与话术中提到的产品属于同一治疗/症状方向 (例: 话术谈「清热解毒」, 搭配只能是清热类中成药; 话术谈「肠胃湿滞」, 搭配只能是肠胃类中成药)\n"
            f"- 不要推荐与话术无关的通用商品 (如维生素C、电子体温计), 除非话术明确涉及\n\n"
            f"格式示例:\n"
            f"【话术】近期湿热感冒, 藿香正气水与保和丸搭配, 既能化湿又能消食, 建议家中常备。\n"
            f"【搭配】建议搭配：藿香正气胶囊 + 保和丸\n"
        )
        resp = _sync_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.5,
        )
        content = (resp.choices[0].message.content or "").strip()
        return _parse_marketing_pair(content, fallback_talk, fallback_upsell)
    except Exception as e:
        log.warning("generate_marketing_pair LLM call failed: %s", e)
        return {"talking_point": fallback_talk, "upsell": fallback_upsell}


def _parse_marketing_pair(content: str, fallback_talk: str, fallback_upsell: str) -> dict:
    """从 LLM 输出解析 【话术】 / 【搭配】 两段, 任一缺失则用兜底。"""
    talk = fallback_talk
    upsell = fallback_upsell
    if not content:
        return {"talking_point": talk, "upsell": upsell}

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    for ln in lines:
        if ln.startswith("【话术】"):
            t = ln[len("【话术】"):].strip()
            if t:
                talk = t
        elif ln.startswith("【搭配】"):
            u = ln[len("【搭配】"):].strip()
            if u:
                # 自动补上「建议搭配:」前缀如果 LLM 漏了
                upsell = u if u.startswith("建议搭配") else f"建议搭配：{u}"

    return {"talking_point": talk, "upsell": upsell}


def _fallback_talking_point(products: list[str]) -> str:
    if not products:
        return "针对当前顾客需求，主动推荐关联商品可提升客单价。"
    p = products[0]
    return f"可向购买 {p} 的顾客主动推荐关联商品，提升连带率。"


def generate_reason(category: str, sku_names: list[str], stock: int, alert_titles: list[str]) -> str:
    """同步: 生成「为什么这个 SKU 现在告急」的 1 句原因 (80 字内, 简体)。
    无 key / 失败时降级为模板。
    """
    if not _sync_client:
        return _fallback_reason(category, stock, alert_titles)
    try:
        ctx_alerts = "；".join(alert_titles[:3]) if alert_titles else "（近期无相关公告）"
        prompt = (
            f"你是一位资深药店店长，给药师解释「为什么这个 SKU 现在告急」。\n"
            f"品类：{category}\n"
            f"商品：{', '.join(sku_names[:5])}\n"
            f"当前库存：{stock} 盒\n"
            f"近期相关公告：{ctx_alerts}\n\n"
            f"请用 1 句中文（80 字以内，简体中文）解释告急原因，"
            f"如有关联公告请直接引用标题关键词；如无则说明仅基于库存水位。\n"
            f"不要添加任何前缀或解释。"
        )
        resp = _sync_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.5,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        log.warning("generate_reason LLM call failed: %s", e)
        return _fallback_reason(category, stock, alert_titles)


def _fallback_reason(category: str, stock: int, alert_titles: list[str]) -> str:
    if alert_titles:
        return f"店内 {category} 库存仅 {stock} 盒，叠加近期「{alert_titles[0]}」等因素需及时补货。"
    return f"店内 {category} 库存仅 {stock} 盒，低于安全水位，需及时补货。"


SENTIMENT_LABELS = ("positive", "neutral", "concern", "negative")


def classify_sentiment(title: str, summary: str = "") -> str | None:
    """同步: 把一条公告分类到 positive / neutral / concern / negative 之一。
    无 key / 失败时返回 None (调用方应回退为 unknown)。
    """
    if not _sync_client:
        return None
    text = (title or "").strip()
    if summary:
        text = f"{text}\n{summary[:200]}"
    if not text:
        return None
    try:
        prompt = (
            f"你是医药行业舆情分析员。请把下面这条公告按情感倾向分类，"
            f"只输出一个标签 (positive / neutral / concern / negative)：\n\n"
            f"标题：{title}\n摘要：{(summary or '')[:200]}\n\n"
            f"规则：\n"
            f"- positive: 政策利好、新药获批、免费接种、便民措施\n"
            f"- neutral: 政策通知、年度报告、监测数据通报、说明性公告\n"
            f"- concern: 上升、上升趋势、聚集、预警、风险提示、流感高峰、ILI 上升\n"
            f"- negative: 召回、严重不良反应、聚集性疫情、死亡、突发公共卫生事件\n\n"
            f"只输出一个词，不要任何其他内容。"
        )
        resp = _sync_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0.1,
        )
        label = (resp.choices[0].message.content or "").strip().lower()
        for s in SENTIMENT_LABELS:
            if s in label:
                return s
        return None
    except Exception as e:
        log.warning("classify_sentiment LLM call failed: %s", e)
        return None


async def stream_chat_pharmacist(
    user_msg: str,
    history: list[dict] | None = None,
    messages: list[dict] | None = None,
) -> AsyncIterator[dict]:
    """
    异步生成器: 流式返回 LLM 增量 dict, 形如 {"content": "..."} 或 {"source": "FAQ-Fallback"}。
    - 上游异常时通过 yield {"source": "FAQ-Fallback", "content": <FAQ>} 一次性返回, 供调用方决定是否中止。
    - 调用方必须在 mid-stream error 时停止累加 full_text。
    - 若 caller 传入 messages, 则直接使用 (RAG 模式); 否则按 system + history + user 组装。
    """
    if not _async_client:
        for chunk in _faq_chunks(user_msg):
            yield chunk
        return

    if messages is None:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if history:
            for h in history[-6:]:
                if "role" in h and "content" in h:
                    messages.append({"role": h["role"], "content": h["content"]})
        messages.append({"role": "user", "content": user_msg})

    try:
        stream = await _async_client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=600,
            temperature=0.5,
            stream=True,
        )
        async for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
            except (AttributeError, IndexError):
                delta = None
            if delta:
                yield {"content": delta}
    except Exception as e:
        log.warning("stream_chat_pharmacist LLM call failed: %s", e)
        async for chunk in _faq_chunks(user_msg):
            yield chunk


def _faq_chunks(user_msg: str) -> list[dict]:
    """无 LLM 时的 FAQ 降级, 一次性返回, 并显式标注 source 便于 UI 区分。"""
    from services.mock_data import chat_reply
    reply = chat_reply(user_msg)
    return [
        {"source": "FAQ-Fallback"},
        {"content": f"（{reply['source']}）\n\n{reply['answer']}"},
    ]
