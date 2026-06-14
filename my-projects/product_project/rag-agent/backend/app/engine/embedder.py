"""向量嵌入器 — 支持 Voyage API / OpenAI 兼容 / 本地 TF-IDF 降级.

三层策略:
    1. Voyage AI  (生产首选，Anthropic 官方)
    2. OpenAI 兼容接口 (通过 EMBEDDING_BASE_URL 配置)
    3. TF-IDF 本地 (零依赖降级)
"""

import os
import math
import time
from typing import Protocol

import httpx

from app.config import llm


# ---------------------------------------------------------------------------
# Embedder 接口
# ---------------------------------------------------------------------------

class Embedder(Protocol):
    """嵌入器接口."""

    @property
    def dimension(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


# ---------------------------------------------------------------------------
# 1. Voyage AI Embedder
# ---------------------------------------------------------------------------

VOYAGE_DIMS = {
    "voyage-3": 1024,
    "voyage-3-lite": 512,
    "voyage-code-3": 2048,
}

VOYAGE_BASE = "https://api.voyageai.com/v1"


class VoyageEmbedder:
    """Voyage AI embedding (Anthropic 官方推荐)."""

    def __init__(self, model: str = "voyage-3"):
        self.model = model
        self._dim = VOYAGE_DIMS.get(model, 1024)

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        resp = httpx.post(
            f"{VOYAGE_BASE}/embeddings",
            headers={
                "Authorization": f"Bearer {llm.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": texts,
                "output_dimension": self._dim,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return [d["embedding"] for d in data["data"]]

    def embed_query(self, text: str) -> list[float]:
        """单条查询嵌入 (Voyage 支持 input_type=query)."""
        resp = httpx.post(
            f"{VOYAGE_BASE}/embeddings",
            headers={
                "Authorization": f"Bearer {llm.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": [text],
                "input_type": "query",
                "output_dimension": self._dim,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


# ---------------------------------------------------------------------------
# 2. OpenAI 兼容 Embedder
# ---------------------------------------------------------------------------

class OpenAICompatibleEmbedder:
    """OpenAI 兼容接口 (DeepSeek, 智谱, 本地 Ollama 等)."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "text-embedding-3-small",
    ):
        self.base_url = (base_url or os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY", llm.api_key)
        self.model = model
        self._dim = 1536  # 默认；首次调用后更新

    @property
    def dimension(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = [d["embedding"] for d in data["data"]]
        if embeddings:
            self._dim = len(embeddings[0])
        return embeddings

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


# ---------------------------------------------------------------------------
# 3. TF-IDF 本地 Embedder (降级)
# ---------------------------------------------------------------------------

class TFIDFEmbedder:
    """本地 TF-IDF — 零外部依赖，当 API 不可用时降级."""

    def __init__(self):
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_count = 0
        self._dim = 0

    @property
    def dimension(self) -> int:
        return self._dim

    def fit(self, texts: list[str]) -> "TFIDFEmbedder":
        from collections import Counter

        doc_freq = Counter()
        for text in texts:
            for token in set(self._tokenize(text)):
                doc_freq[token] += 1

        self.vocab = {word: i for i, word in enumerate(doc_freq.keys())}
        self._dim = len(self.vocab)
        self.doc_count = len(texts)

        for word, df in doc_freq.items():
            self.idf[word] = math.log((self.doc_count + 1) / (df + 1)) + 1

        return self

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._encode(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._encode(text)

    def _encode(self, text: str) -> list[float]:
        from collections import Counter

        tokens = self._tokenize(text)
        tf = Counter(tokens)
        vec = [0.0] * self._dim
        for word, count in tf.items():
            if word in self.vocab:
                tf_val = count / len(tokens) if tokens else 0
                vec[self.vocab[word]] = tf_val * self.idf.get(word, 0)
        return vec

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
# 工厂
# ---------------------------------------------------------------------------

# 用于标记当前使用哪个后端
EMBEDDER_BACKEND = ""

_embedder_cache: Embedder | None = None


def get_embedder() -> Embedder:
    """获取嵌入器实例 (单例)."""
    global _embedder_cache, EMBEDDER_BACKEND

    if _embedder_cache is not None:
        return _embedder_cache

    # 策略 1: Voyage AI
    if os.getenv("EMBEDDING_MODEL", "").startswith("voyage"):
        try:
            emb = VoyageEmbedder(llm.embedding_model)
            # 快速探测
            emb.embed_query("ping")
            EMBEDDER_BACKEND = "voyage"
            _embedder_cache = emb
            return emb
        except Exception:
            pass

    # 策略 2: OpenAI 兼容
    emb_base = os.getenv("EMBEDDING_BASE_URL", "")
    if emb_base or os.getenv("EMBEDDING_API_KEY", ""):
        try:
            emb = OpenAICompatibleEmbedder()
            emb.embed_query("ping")
            EMBEDDER_BACKEND = "openai_compatible"
            _embedder_cache = emb
            return emb
        except Exception:
            pass

    # 策略 3: 降级 TF-IDF
    EMBEDDER_BACKEND = "tfidf"
    _embedder_cache = TFIDFEmbedder()
    return _embedder_cache


def reset_embedder() -> None:
    global _embedder_cache, EMBEDDER_BACKEND
    _embedder_cache = None
    EMBEDDER_BACKEND = ""
