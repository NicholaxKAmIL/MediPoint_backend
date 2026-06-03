"""
AI 药师助手 — SSE 流式对话 API (RAG 版)
- POST /api/chat  ->  text/event-stream
- 事件: start / delta / references / end / error
- 失败时降级为 FAQ 一次性返回 (source=FAQ-Fallback)
- 引用完整性: 流式过程中剔除不在参考资料编号内的 [n]
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services import rag, rag_prompt
from util.auth import verify_credentials
from util.llm import stream_chat_pharmacist

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# 服务端固定 retrieval 深度 (不再由客户端控制)
CHAT_TOP_K = 5
# RAG 检索结果相关性阈值 — 低于此视为"未检索到有效资料", 走通用 LLM
RAG_TOP_SCORE_THRESHOLD = 0.20
RAG_AVG_SCORE_THRESHOLD = 0.10
# 允许的引用编号, 用于剔除伪造 [n]
_CITATION_RE = re.compile(r"\[(\d+)\]")


def _is_rag_relevant(retrieved: list[dict]) -> bool:
    """RAG 检索结果是否足够相关 — 至少 top-1 强或 top-3 平均强才视为可参考。"""
    if not retrieved:
        return False
    top1 = float(retrieved[0].get("score", 0.0))
    if top1 >= RAG_TOP_SCORE_THRESHOLD:
        return True
    top3 = [float(r.get("score", 0.0)) for r in retrieved[:3]]
    avg3 = sum(top3) / len(top3) if top3 else 0.0
    return avg3 >= RAG_AVG_SCORE_THRESHOLD


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[dict] | None = Field(default=None, max_length=20)


def _sse(event: str, data: dict) -> str:
    payload = {"type": event, **data}
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _mask_fabricated_citations(text: str, valid_n: int) -> str:
    """剔除 LLM 输出中超出参考资料编号范围的 [n] 引用, 避免幻觉引用。"""
    if not text or valid_n <= 0:
        return text

    def _sub(m: re.Match) -> str:
        n = int(m.group(1))
        return m.group(0) if 1 <= n <= valid_n else ""

    return _CITATION_RE.sub(_sub, text)


async def _stream(req: ChatRequest) -> AsyncIterator[str]:
    start = time.time()
    source = "DeepSeek-RAG"
    full_text = ""
    retrieved: list[dict] = []
    rag_used = False
    references_emitted = False
    errored = False

    # 1) RAG 检索 + 相关性判断 (在 start 事件之前, 决定 source 标签)
    try:
        retrieved = rag.retrieve(req.message, top_k=CHAT_TOP_K)
    except Exception as e:
        log.warning("RAG retrieve failed: %s", e)
        retrieved = []

    valid_n = len(retrieved)
    rag_relevant = _is_rag_relevant(retrieved)

    # 2) 拼装 messages — RAG 相关时注入参考资料, 否则走通用 LLM 路径
    if rag_relevant:
        rag_used = True
        messages = rag_prompt.build_messages(req.message, retrieved, history=req.history)
    else:
        if retrieved:
            top1 = float(retrieved[0].get("score", 0.0))
            top3_avg = sum(float(r.get("score", 0.0)) for r in retrieved[:3]) / min(3, len(retrieved))
            log.info(
                "RAG 结果弱相关 (top1=%.3f, top3_avg=%.3f), 改用通用 LLM: %s",
                top1, top3_avg, req.message[:60],
            )
            retrieved = []  # 弱相关则不暴露给前端, 避免误导 grounding
            valid_n = 0
        source = "DeepSeek-General"
        messages = None  # 让 llm.py 走默认 system+history+user 路径

    yield _sse("start", {"source": source})

    # 3) 调用 LLM (流式, 引用完整性过滤)
    try:
        async for chunk in stream_chat_pharmacist(req.message, req.history or [], messages=messages):
            content = chunk.get("content")
            if not content:
                if chunk.get("source"):
                    source = chunk["source"]
                continue
            # 成功流出首个 delta 后才发 references (避免 LLM 失败时误导)
            if not references_emitted and retrieved:
                refs = rag_prompt.build_references(retrieved)
                yield _sse("references", {"items": refs})
                references_emitted = True
            content = _mask_fabricated_citations(content, valid_n)
            full_text += content
            yield _sse("delta", {"content": content})
    except Exception:
        log.exception("chat stream failed")
        errored = True
        yield _sse("error", {"message": "上游服务暂时不可用, 请稍后再试。"})

    # 4) end 事件: 决定 references 是否带回
    if errored:
        # LLM 失败时 references 必须清空, 避免误标 grounding
        yield _sse("references", {"items": []})
        full_text_masked = _mask_fabricated_citations(full_text, valid_n)
        # end 事件不带 references (前端已收到空)
        yield _sse("end", {
            "source": source,
            "duration_ms": int((time.time() - start) * 1000),
            "full_text": full_text_masked,
            "rag_used": False,
            "retrieved_count": 0,
        })
    else:
        if not references_emitted:
            # LLM 没产出 delta (空响应) 但没抛错: 仍把 references 发出去
            if retrieved:
                refs = rag_prompt.build_references(retrieved)
                yield _sse("references", {"items": refs})
            else:
                yield _sse("references", {"items": []})
        yield _sse("end", {
            "source": source,
            "duration_ms": int((time.time() - start) * 1000),
            "full_text": full_text,
            "rag_used": rag_used,
            "retrieved_count": valid_n,
        })


@router.post("", dependencies=[Depends(verify_credentials)])
async def chat(req: ChatRequest):
    """SSE 流式聊天。 Content-Type: text/event-stream"""
    return StreamingResponse(
        _stream(req),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
