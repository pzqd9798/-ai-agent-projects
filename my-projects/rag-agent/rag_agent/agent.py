"""RAG Agent — 检索增强生成的主循环."""

import os
import time
from dataclasses import dataclass, field
from anthropic import Anthropic

from .ingestion import ingest_file, ingest_directory, Chunk
from .vector_store import InMemoryVectorStore, create_vector_store
from .memory import MemoryManager


@dataclass
class RAGResponse:
    answer: str
    sources: list[str] = field(default_factory=list)
    retrieved_count: int = 0
    elapsed_ms: float = 0


# ---------------------------------------------------------------------------
# RAG Agent
# ---------------------------------------------------------------------------

RAG_SYSTEM_PROMPT = """你是一个知识助手 Agent，配备了 RAG (检索增强生成) 能力。

规则:
- 优先使用检索到的文档内容回答问题
- 如果文档中没有相关信息，如实说明，不要编造
- 引用来源时标注文件名
- 结合用户的偏好和历史记忆提供个性化回答
- 用中文回复，除非用户用其他语言提问
- 回复简洁、准确、有条理"""


class RAGAgent:
    """RAG Agent: 检索 → 增强 → 生成."""

    def __init__(
        self,
        redis_url: str = "",
        system_prompt: str = RAG_SYSTEM_PROMPT,
    ):
        self.vector_store = create_vector_store(redis_url)
        self.memory = MemoryManager()
        self.system_prompt = system_prompt
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv()
            self._client = Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
            )
        return self._client

    @property
    def model(self) -> str:
        return os.getenv("MODEL_ID", "claude-sonnet-4-6")

    # ------------------------------------------------------------------
    # 文档管理
    # ------------------------------------------------------------------

    def ingest_file(self, file_path: str) -> int:
        chunks = ingest_file(file_path)
        self.vector_store.add_chunks(chunks)
        return len(chunks)

    def ingest_directory(self, dir_path: str) -> int:
        chunks = ingest_directory(dir_path)
        self.vector_store.add_chunks(chunks)
        return len(chunks)

    # ------------------------------------------------------------------
    # 核心 RAG 管道
    # ------------------------------------------------------------------

    def query(self, question: str, top_k: int = 5) -> RAGResponse:
        """执行完整的 RAG 管道: 检索 → 增强 → 生成."""
        t0 = time.time()

        # 1. 检索
        retrieved = self.vector_store.search(question, top_k=top_k)

        # 2. 构建增强上下文
        rag_context = self.memory.build_rag_context(question, retrieved)

        # 3. 构建消息
        user_message = question
        if rag_context:
            user_message = f"{rag_context}\n\n---\n\n## ❓ 用户问题\n\n{question}"

        messages = self.memory.short_term.as_messages()
        messages.append({"role": "user", "content": user_message})

        # 4. 调用 LLM
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=self.system_prompt,
            messages=messages,
        )

        # 5. 提取回答
        answer = ""
        for block in response.content:
            if hasattr(block, "text"):
                answer += block.text

        # 6. 更新记忆
        self.memory.add_user_message(question)
        self.memory.add_assistant_message(answer)
        self.memory.auto_extract_memory(question, answer)

        sources = list(set(c.source for c, _ in retrieved))
        elapsed = (time.time() - t0) * 1000

        return RAGResponse(
            answer=answer,
            sources=sources,
            retrieved_count=len(retrieved),
            elapsed_ms=elapsed,
        )

    # ------------------------------------------------------------------
    # 会话管理
    # ------------------------------------------------------------------

    def save_memory(self, filepath: str) -> None:
        self.memory.long_term.save(filepath)

    def load_memory(self, filepath: str) -> None:
        self.memory.long_term.load(filepath)

    def clear_conversation(self) -> None:
        self.memory.short_term.clear()

    def stats(self) -> dict:
        vs = self.vector_store.stats()
        return {
            **vs,
            "short_term_turns": len(self.memory.short_term),
            "long_term_facts": len(self.memory.long_term.get_facts()),
            "preferences": len(self.memory.long_term.all_preferences()),
        }
