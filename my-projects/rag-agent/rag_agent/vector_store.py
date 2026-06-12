"""向量存储 — 嵌入式检索.

提供两种实现:
    InMemoryVectorStore — 内存余弦相似度 (入门, 零依赖)
    AnthropicEmbedder — 使用 Anthropic API 生成 embedding (实际上用简单的 TF-IDF 近似)
"""

import math
import os
import json
from collections import Counter
from .ingestion import Chunk


# ---------------------------------------------------------------------------
# 轻量级 TF-IDF 向量化 (零外部依赖)
# ---------------------------------------------------------------------------

class SimpleEmbedder:
    """基于 TF-IDF 的轻量级文本向量化.

    不需要 embedding API, 适合本地演示.
    生产环境替换为真实 embedding 模型.
    """

    def __init__(self):
        self.vocab: dict[str, int] = {}    # word -> index
        self.idf: dict[str, float] = {}    # word -> idf
        self.doc_count = 0

    def fit(self, texts: list[str]) -> "SimpleEmbedder":
        """在语料上构建词汇表和 IDF."""
        doc_freq = Counter()
        tokenized_docs = []

        for text in texts:
            tokens = self._tokenize(text)
            tokenized_docs.append(tokens)
            for token in set(tokens):
                doc_freq[token] += 1

        # 构建词汇表
        self.vocab = {word: i for i, word in enumerate(doc_freq.keys())}
        self.doc_count = len(texts)

        # 计算 IDF
        for word, df in doc_freq.items():
            self.idf[word] = math.log((self.doc_count + 1) / (df + 1)) + 1

        return self

    def encode(self, text: str) -> list[float]:
        """将文本编码为 TF-IDF 向量."""
        tokens = self._tokenize(text)
        tf = Counter(tokens)
        vec = [0.0] * len(self.vocab)
        for word, count in tf.items():
            if word in self.vocab:
                tf_val = count / len(tokens) if tokens else 0
                vec[self.vocab[word]] = tf_val * self.idf.get(word, 0)
        return vec

    def _tokenize(self, text: str) -> list[str]:
        """简易中文/英文分词."""
        import re
        # 英文: 拆分单词，中文: 逐字 + 2-gram
        tokens = []
        # 英文单词
        for m in re.finditer(r"[a-zA-Z0-9]+", text.lower()):
            tokens.append(m.group())
        # 中文字符 2-gram
        chinese = re.findall(r"[一-鿿]+", text)
        for segment in chinese:
            for i in range(len(segment)):
                if i < len(segment) - 1:
                    tokens.append(segment[i:i + 2])
                tokens.append(segment[i])
        return tokens


# ---------------------------------------------------------------------------
# 内存向量存储
# ---------------------------------------------------------------------------

class InMemoryVectorStore:
    """内存向量存储 — 余弦相似度检索."""

    def __init__(self, embedder: SimpleEmbedder | None = None):
        self.embedder = embedder or SimpleEmbedder()
        self._chunks: list[Chunk] = []
        self._vectors: list[list[float]] = []
        self._fitted = False

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """添加 chunks 并拟合嵌入器."""
        if self._chunks:
            # 增量添加：重新拟合
            all_texts = [c.text for c in self._chunks] + [c.text for c in chunks]
            self.embedder.fit(all_texts)
            # 重新编码已有向量
            self._vectors = [self.embedder.encode(c.text) for c in self._chunks]
        else:
            self.embedder.fit([c.text for c in chunks])

        for c in chunks:
            self._chunks.append(c)
            self._vectors.append(self.embedder.encode(c.text))
        self._fitted = True

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        """余弦相似度搜索, 返回 (chunk, score) 列表."""
        if not self._fitted:
            return []

        query_vec = self.embedder.encode(query)
        scored = []
        for i, vec in enumerate(self._vectors):
            score = self._cosine_sim(query_vec, vec)
            if score > 0:
                scored.append((self._chunks[i], score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()
        self._fitted = False

    def stats(self) -> dict:
        return {
            "total_chunks": len(self._chunks),
            "total_sources": len(set(c.source for c in self._chunks)),
            "vocab_size": len(self.embedder.vocab),
        }

    def list_sources(self) -> list[str]:
        return sorted(set(c.source for c in self._chunks))


# ---------------------------------------------------------------------------
# Redis 向量存储 (可选, 生产用)
# ---------------------------------------------------------------------------

class RedisVectorStore:
    """基于 Redis 的向量存储 — 持久化, 支持大规模语料."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        import redis
        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.embedder = SimpleEmbedder()
        self._chunks: list[Chunk] = []
        self._fitted = False

    def add_chunks(self, chunks: list[Chunk]) -> None:
        all_texts = [c.text for c in self._chunks] + [c.text for c in chunks]
        self.embedder.fit(all_texts)

        for c in chunks:
            vec = self.embedder.encode(c.text)
            self.redis.hset(
                f"rag:chunk:{c.id}",
                mapping={
                    "text": c.text, "source": c.source,
                    "chunk_index": c.chunk_index,
                    "metadata": json.dumps(c.metadata, ensure_ascii=False),
                    "vector": json.dumps(vec),
                }
            )
            self._chunks.append(c)
        self._fitted = True

    def search(self, query: str, top_k: int = 5) -> list[tuple[Chunk, float]]:
        if not self._fitted:
            return []
        query_vec = self.embedder.encode(query)

        # 扫描所有 chunk (小规模; 生产应使用 Redis 向量索引)
        scored = []
        for c in self._chunks:
            data = self.redis.hgetall(f"rag:chunk:{c.id}")
            if data and "vector" in data:
                vec = json.loads(data["vector"])
                dot = sum(x * y for x, y in zip(query_vec, vec))
                na = math.sqrt(sum(x * x for x in query_vec))
                nb = math.sqrt(sum(y * y for y in vec))
                score = dot / (na * nb) if na and nb else 0.0
                if score > 0:
                    scored.append((c, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def clear(self) -> None:
        for c in self._chunks:
            self.redis.delete(f"rag:chunk:{c.id}")
        self._chunks.clear()
        self._fitted = False

    def stats(self) -> dict:
        return {
            "total_chunks": len(self._chunks),
            "total_sources": len(set(c.source for c in self._chunks)),
            "vocab_size": len(self.embedder.vocab),
            "backend": "redis",
        }


# ---------------------------------------------------------------------------
# 工厂
# ---------------------------------------------------------------------------

def create_vector_store(redis_url: str = "") -> InMemoryVectorStore:
    """创建向量存储实例，优先使用 Redis."""
    if redis_url:
        try:
            import redis
            r = redis.Redis.from_url(redis_url)
            r.ping()
            return RedisVectorStore(redis_url)
        except Exception:
            pass
    return InMemoryVectorStore()
