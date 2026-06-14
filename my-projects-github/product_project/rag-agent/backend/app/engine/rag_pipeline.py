"""RAG 管道 — 检索 → 混合重排 → 上下文组装 → LLM 生成.

核心管道:
    1. 向量检索 (语义相似度)
    2. BM25 混合重排 (关键词 + 语义融合)
    3. 上下文组装 (记忆 + 检索结果)
    4. LLM 增强生成
"""

import math
import time
import os
from dataclasses import dataclass, field

from anthropic import Anthropic

from app.config import llm, retrieval
from app.engine.embedder import get_embedder, Embedder, TFIDFEmbedder
from app.engine.chunker import ChunkData
from app.engine.hybrid_search import HybridSearcher


# ---------------------------------------------------------------------------
# 管道结果
# ---------------------------------------------------------------------------

@dataclass
class RAGResult:
    answer: str
    sources: list[dict] = field(default_factory=list)   # [{filename, chunk_index, score, snippet}]
    retrieved_count: int = 0
    elapsed_ms: float = 0


# ---------------------------------------------------------------------------
# 系统提示词
# ---------------------------------------------------------------------------

RAG_SYSTEM_PROMPT = """你是一个企业级 RAG 知识助手，配备了检索增强生成能力。

## 核心规则
1. **优先使用检索到的文档内容**回答问题，不要编造
2. 如果文档中没有相关信息，**如实说明**，并提供你确实知道的相关知识
3. 引用来源时标注**文件名和片段编号**
4. 结合用户的**偏好和历史记忆**提供个性化回答
5. 用**中文**回复，除非用户用其他语言提问
6. 回复要**简洁、准确、有条理**，使用 Markdown 格式化

## 回答结构
- 先给出直接答案
- 再列出支持证据 (引用来源)
- 如果信息不足，明确告知并给出建议"""


# ---------------------------------------------------------------------------
# RAG 管道
# ---------------------------------------------------------------------------

class RAGPipeline:
    """检索增强生成管道.

    用法:
        pipeline = RAGPipeline()
        pipeline.index_chunks(chunks)
        result = pipeline.query("什么是 RAG?")
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        system_prompt: str = RAG_SYSTEM_PROMPT,
    ):
        self.embedder = embedder or get_embedder()
        self.system_prompt = system_prompt
        self._chunks: list[ChunkData] = []
        self._vectors: list[list[float]] = []
        self._hybrid: HybridSearcher | None = None
        self._client: Anthropic | None = None

    # ------------------------------------------------------------------
    # 索引
    # ------------------------------------------------------------------

    def index_chunks(self, chunks: list[ChunkData]) -> int:
        """索引一批 chunks，返回总数."""
        texts = [c.text for c in chunks]

        # 对 TF-IDF 嵌入器需要先 fit
        if isinstance(self.embedder, TFIDFEmbedder):
            all_texts = [c.text for c in self._chunks] + texts
            self.embedder.fit(all_texts)
            # 重新编码已有向量
            if self._chunks:
                self._vectors = self.embedder.embed([c.text for c in self._chunks])

        # 批量嵌入新文本
        new_vectors = self.embedder.embed(texts)
        for chunk, vec in zip(chunks, new_vectors):
            chunk.embedding = vec

        self._chunks.extend(chunks)
        self._vectors.extend(new_vectors)

        # 重建混合检索索引
        self._hybrid = HybridSearcher().index([c.text for c in self._chunks])

        return len(self._chunks)

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def retrieve(self, query: str, top_k: int | None = None) -> list[tuple[ChunkData, float]]:
        """检索 top_k 个最相关的 chunks."""
        top_k = top_k or retrieval.top_k

        if not self._chunks:
            return []

        # 1. 向量分数
        query_vec = self.embedder.embed_query(query)
        vec_scores = [self._cosine_sim(query_vec, v) for v in self._vectors]

        # 2. 混合重排
        if self._hybrid:
            fused = self._hybrid.search(query, vec_scores)
        else:
            fused = vec_scores

        # 3. 排序取 top_k
        indexed = list(enumerate(fused))
        indexed.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed[:top_k]:
            if score > 0:
                results.append((self._chunks[idx], score))

        return results

    # ------------------------------------------------------------------
    # 完整 RAG 查询
    # ------------------------------------------------------------------

    def query(
        self,
        question: str,
        top_k: int | None = None,
        context_memory: str = "",          # 长期记忆文本
        history_messages: list[dict] | None = None,
    ) -> RAGResult:
        """执行完整 RAG 管道."""
        t0 = time.time()

        # 1. 检索
        retrieved = self.retrieve(question, top_k)

        # 2. 构建增强上下文
        augmented_context = self._build_context(question, retrieved, context_memory)

        # 3. 构建消息
        messages = list(history_messages or [])
        messages.append({"role": "user", "content": augmented_context})

        # 4. LLM 生成
        answer = self._generate(messages)

        # 5. 构建结果
        sources = [
            {
                "filename": c.source,
                "chunk_index": c.chunk_index,
                "score": round(score, 4),
                "snippet": c.text[:200] + ("..." if len(c.text) > 200 else ""),
            }
            for c, score in retrieved
        ]

        elapsed = (time.time() - t0) * 1000

        return RAGResult(
            answer=answer,
            sources=sources,
            retrieved_count=len(retrieved),
            elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # 纯检索 (不生成)
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """仅检索，不生成回答."""
        retrieved = self.retrieve(query, top_k)
        return [
            {
                "chunk_id": c.id,
                "text": c.text,
                "source": c.source,
                "score": round(score, 4),
                "metadata": c.metadata,
            }
            for c, score in retrieved
        ]

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _build_context(
        self,
        question: str,
        retrieved: list[tuple[ChunkData, float]],
        memory_context: str = "",
    ) -> str:
        """构建增强上下文 (检索结果 + 记忆 + 问题)."""
        parts = []

        # 检索结果
        if retrieved:
            chunks_text = []
            total_chars = 0
            max_chars = retrieval.max_context_tokens * 3  # ~chars per token

            for chunk, score in retrieved:
                snippet = (
                    f"[来源: {chunk.source}#{chunk.chunk_index}, "
                    f"相关度: {score:.2f}]\n{chunk.text}"
                )
                if total_chars + len(snippet) < max_chars:
                    chunks_text.append(snippet)
                    total_chars += len(snippet)
                else:
                    break

            parts.append(
                "## 📄 相关知识 (从文档中检索)\n\n"
                + "\n\n---\n\n".join(chunks_text)
            )

        # 长期记忆
        if memory_context:
            parts.append(memory_context)

        # 问题
        parts.append(f"## ❓ 用户问题\n\n{question}")

        return "\n\n".join(parts)

    def _generate(self, messages: list[dict]) -> str:
        """调用 LLM 生成回答."""
        if self._client is None:
            api_key = llm.api_key or os.getenv("ANTHROPIC_API_KEY", "")
            base_url = llm.base_url or os.getenv("ANTHROPIC_BASE_URL") or None

            if not api_key:
                return "[错误] 未配置 LLM API Key，请设置 ANTHROPIC_API_KEY"

            self._client = Anthropic(api_key=api_key, base_url=base_url)

        try:
            response = self._client.messages.create(
                model=llm.model_id,
                max_tokens=llm.max_tokens,
                system=self.system_prompt,
                messages=messages,
            )
        except Exception as exc:
            return f"[错误] LLM 调用失败: {exc}"

        answer = ""
        for block in response.content:
            if hasattr(block, "text"):
                answer += block.text

        return answer

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a)) if a else 0
        nb = math.sqrt(sum(y * y for y in b)) if b else 0
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    # ------------------------------------------------------------------
    # 管理
    # ------------------------------------------------------------------

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)

    @property
    def source_files(self) -> list[str]:
        return sorted(set(c.source for c in self._chunks))

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()
        self._hybrid = None

    def stats(self) -> dict:
        return {
            "total_chunks": len(self._chunks),
            "total_sources": len(set(c.source for c in self._chunks)),
            "backend": type(self.embedder).__name__,
        }
