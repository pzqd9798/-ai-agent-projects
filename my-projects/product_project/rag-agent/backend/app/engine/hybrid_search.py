"""混合检索 — BM25 关键词 + 向量语义 加权融合.

BM25 实现参考 Robertson & Zaragoza (2009).
"""

import math
from collections import Counter

from app.config import retrieval


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------

class BM25:
    """BM25 关键词检索."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self._docs: list[list[str]] = []
        self._avgdl: float = 0
        self._df: dict[str, int] = {}    # document frequency
        self._idf: dict[str, float] = {}
        self._tokens: list[list[str]] = []
        self._N = 0

    def index(self, documents: list[str]) -> "BM25":
        self._N = len(documents)
        self._tokens = [self._tokenize(d) for d in documents]
        self._docs = self._tokens

        # 平均文档长度
        self._avgdl = sum(len(t) for t in self._tokens) / max(self._N, 1)

        # DF (文档频率)
        self._df = {}
        for tokens in self._tokens:
            for word in set(tokens):
                self._df[word] = self._df.get(word, 0) + 1

        # IDF
        self._idf = {}
        for word, freq in self._df.items():
            self._idf[word] = math.log(
                (self._N - freq + 0.5) / (freq + 0.5) + 1
            )

        return self

    def search(self, query: str) -> list[float]:
        """返回每个文档的 BM25 分数."""
        if self._N == 0:
            return []

        query_tokens = self._tokenize(query)
        scores = []

        for doc_tokens in self._tokens:
            doc_len = len(doc_tokens)
            if doc_len == 0:
                scores.append(0.0)
                continue

            tf = Counter(doc_tokens)
            score = 0.0
            for token in query_tokens:
                if token not in self._idf:
                    continue
                f = tf.get(token, 0)
                score += self._idf[token] * (
                    f * (self.k1 + 1) /
                    (f + self.k1 * (1 - self.b + self.b * doc_len / self._avgdl))
                )
            scores.append(score)

        return scores

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        import re
        tokens = []
        for m in re.finditer(r"[a-zA-Z0-9]+", text.lower()):
            tokens.append(m.group())
        chinese = re.findall(r"[一-鿿]+", text)
        for seg in chinese:
            for i in range(len(seg)):
                if i < len(seg) - 1:
                    tokens.append(seg[i:i + 2])
                tokens.append(seg[i])
        return tokens


# ---------------------------------------------------------------------------
# 混合检索器
# ---------------------------------------------------------------------------

class HybridSearcher:
    """BM25 + 向量语义混合检索.

    score = alpha * vec_score + (1 - alpha) * bm25_score
    alpha = 1.0 → 纯向量
    alpha = 0.0 → 纯关键词
    """

    def __init__(self, alpha: float | None = None):
        self.alpha = alpha if alpha is not None else retrieval.hybrid_alpha
        self.bm25 = BM25()
        self._texts: list[str] = []

    def index(self, texts: list[str]) -> "HybridSearcher":
        self._texts = texts
        self.bm25.index(texts)
        return self

    def search(
        self,
        query: str,
        vector_scores: list[float],
    ) -> list[float]:
        """融合 BM25 和向量分数.

        vector_scores 必须与 index() 的 texts 顺序一致.
        """
        bm25_scores = self.bm25.search(query)
        n = max(len(bm25_scores), len(vector_scores))
        fused = []

        for i in range(n):
            v = vector_scores[i] if i < len(vector_scores) else 0.0
            b = bm25_scores[i] if i < len(bm25_scores) else 0.0

            # 归一化
            v = max(0.0, min(1.0, v))
            b = self._normalize_bm25(b, bm25_scores)

            fused.append(self.alpha * v + (1 - self.alpha) * b)

        return fused

    @staticmethod
    def _normalize_bm25(score: float, all_scores: list[float]) -> float:
        max_s = max(all_scores) if all_scores else 1.0
        if max_s == 0:
            return 0.0
        return score / max_s
