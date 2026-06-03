"""
TF-IDF + Jieba 中文检索器 — 替代 Embedding + VectorDB 的轻量方案。
- 进程内 in-memory 索引, 重启需 reindex。
- 250 chunks 量级下 < 10ms / query。
- 未来可替换为 ChromaDB / bge-m3。
"""
from __future__ import annotations

import logging
import threading

import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

log = logging.getLogger(__name__)

# 医药领域自定义词典, 提高切词准确率
_CUSTOM_WORDS = [
    "连花清瘟", "布洛芬", "美林", "对乙酰氨基酚", "藿香正气",
    "奥司他韦", "氯雷他定", "西替利嗪", "奥美拉唑", "铝碳酸镁",
    "氨溴索", "右美沙芬", "复方甘草", "维C银翘", "板蓝根",
    "抗病毒", "抗生素", "处方药", "OTC", "联合用药",
    "流感", "高血压", "糖尿病", "过敏性鼻炎", "手足口病",
    "不良反应", "GSP", "NMPA", "电子处方", "医保",
    "执业药师", "药师", "处方", "雾化",
    "SGLT2", "DPP-4", "二甲双胍", "沙坦", "地平",
]
for _w in _CUSTOM_WORDS:
    jieba.add_word(_w)


def _tokenize(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    return [t for t in jieba.cut(text) if t.strip()]


class TfidfRetriever:
    """进程级单例 TF-IDF 检索器。"""

    def __init__(self):
        self._lock = threading.RLock()
        self._vectorizer: TfidfVectorizer | None = None
        self._matrix = None
        self._chunks: list[dict] = []
        self._id_to_idx: dict[str, int] = {}

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._chunks)

    def index(self, chunks: list[dict]) -> int:
        """全量重建索引。chunks = [{id, text, metadata}, ...]"""
        with self._lock:
            texts = [c.get("text", "") for c in chunks]
            self._chunks = list(chunks)
            self._id_to_idx = {c["id"]: i for i, c in enumerate(chunks) if "id" in c}
            self._vectorizer = TfidfVectorizer(
                tokenizer=_tokenize,
                token_pattern=None,
                lowercase=False,
                ngram_range=(1, 2),
                min_df=1,
            )
            self._matrix = self._vectorizer.fit_transform(texts)
            log.info("TF-IDF retriever indexed %d chunks, vocab=%d",
                     len(texts), len(self._vectorizer.vocabulary_))
            return len(texts)

    def search(
        self,
        query: str,
        top_k: int = 5,
        source_type_filter: list[str] | None = None,
        min_score: float = 0.05,
    ) -> list[dict]:
        """检索 top_k 相似 chunk。可选 source_type 过滤 (alert/drug/faq/sop)。"""
        with self._lock:
            if not self._chunks or self._matrix is None or self._vectorizer is None:
                return []
            q_vec = self._vectorizer.transform([query])
            sims = cosine_similarity(q_vec, self._matrix)[0]
            if source_type_filter:
                mask = np.array([
                    1.0 if c.get("metadata", {}).get("source_type") in source_type_filter
                    else 0.0
                    for c in self._chunks
                ])
                sims = sims * mask
            top_idx = sims.argsort()[::-1][:top_k]
            results = []
            for i in top_idx:
                score = float(sims[i])
                if score < min_score:
                    continue
                c = self._chunks[i]
                results.append({
                    "id": c.get("id", f"chunk-{i}"),
                    "text": c.get("text", ""),
                    "metadata": c.get("metadata", {}),
                    "score": score,
                })
            return results


# 进程级单例
retriever = TfidfRetriever()
