"""记忆服务 — 短期对话流 + 长期用户记忆 (SQLite 持久化).

原先 rag_agent/memory.py 的全内存版本，现在升级为数据库持久化。
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import UserMemory, ChatMessage


# ---------------------------------------------------------------------------
# 短期记忆 (滑动窗口 — 内存)
# ---------------------------------------------------------------------------

@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


class ShortTermMemory:
    """短期对话记忆 — 滑动窗口 (内存)."""

    def __init__(self, max_turns: int = 20):
        self.max_turns = max_turns
        self._turns: list[ConversationTurn] = []

    def add(self, role: str, content: str) -> None:
        self._turns.append(ConversationTurn(role=role, content=content))
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

    def get_recent(self, limit: int | None = None) -> list[ConversationTurn]:
        lim = limit or self.max_turns
        return self._turns[-lim:]

    def as_messages(self) -> list[dict]:
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def clear(self) -> None:
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)


# ---------------------------------------------------------------------------
# 长期记忆 (SQLite 持久化)
# ---------------------------------------------------------------------------

class LongTermMemory:
    """长期记忆 — 偏好、事实、会话摘要 (数据库持久化)."""

    def __init__(self, user_id: int, db):
        self.user_id = user_id
        self.db = db
        self._cache: dict[str, list] = {
            "preference": [],
            "fact": [],
            "session_summary": [],
        }
        self._loaded = False

    async def load(self) -> None:
        """从数据库加载记忆到缓存."""
        result = await self.db.execute(
            select(UserMemory).where(UserMemory.user_id == self.user_id)
        )
        rows = result.scalars().all()
        self._cache = {"preference": [], "fact": [], "session_summary": []}
        for row in rows:
            if row.memory_type in self._cache:
                self._cache[row.memory_type].append({
                    "id": row.id,
                    "key": row.key,
                    "value": row.value,
                })
        self._loaded = True

    async def _ensure_loaded(self) -> None:
        if not self._loaded:
            await self.load()

    async def set_preference(self, key: str, value: str) -> None:
        await self._ensure_loaded()
        mem = UserMemory(
            user_id=self.user_id, memory_type="preference",
            key=key, value=value,
        )
        self.db.add(mem)
        await self.db.commit()

    async def get_preferences(self) -> dict[str, str]:
        await self._ensure_loaded()
        return {m["key"]: m["value"] for m in self._cache["preference"]}

    async def add_fact(self, fact: str) -> None:
        await self._ensure_loaded()
        mem = UserMemory(
            user_id=self.user_id, memory_type="fact",
            key="", value=fact,
        )
        self.db.add(mem)
        await self.db.commit()

    async def get_facts(self) -> list[str]:
        await self._ensure_loaded()
        return [m["value"] for m in self._cache["fact"]]

    async def add_session_summary(self, summary: str) -> None:
        await self._ensure_loaded()
        mem = UserMemory(
            user_id=self.user_id, memory_type="session_summary",
            key="", value=summary,
        )
        self.db.add(mem)
        await self.db.commit()

    async def get_recent_summaries(self, limit: int = 5) -> list[str]:
        await self._ensure_loaded()
        items = self._cache["session_summary"][-limit:]
        return [m["value"] for m in items]

    async def build_context_text(self) -> str:
        """构建注入 LLM 的长期记忆上下文."""
        await self._ensure_loaded()
        parts = []

        prefs = await self.get_preferences()
        if prefs:
            parts.append("## 用户偏好\n" + "\n".join(
                f"- {k}: {v}" for k, v in prefs.items()
            ))

        facts = await self.get_facts()
        if facts:
            parts.append("## 用户相关事实\n" + "\n".join(
                f"- {f}" for f in facts
            ))

        summaries = await self.get_recent_summaries()
        if summaries:
            parts.append("## 历史会话摘要\n" + "\n".join(
                f"- {s}" for s in summaries
            ))

        return "\n\n".join(parts) if parts else ""

    async def auto_extract(self, user_message: str, assistant_reply: str) -> None:
        """从对话中自动提取偏好和事实 (规则引擎)."""
        # 检测偏好表达
        pref_patterns = [
            r"我(喜欢|偏爱|常用|习惯用)\s*(.+?)(?:[。，,;]|$)",
            r"我(是|做|从事)\s*(.+?)(?:[。，,;]|$)",
        ]
        for pattern in pref_patterns:
            for m in re.finditer(pattern, user_message):
                await self.add_fact(m.group(0))

        if "我记住了" in assistant_reply or "已记住" in assistant_reply:
            await self.add_fact(user_message)


# ---------------------------------------------------------------------------
# 记忆管理器
# ---------------------------------------------------------------------------

class MemoryManager:
    """统一短期 + 长期记忆管理."""

    def __init__(self, user_id: int, db):
        self.user_id = user_id
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(user_id, db)

    async def add_user_message(self, content: str) -> None:
        self.short_term.add("user", content)

    async def add_assistant_message(self, content: str) -> None:
        self.short_term.add("assistant", content)

    async def build_context(self, query: str, retrieved_chunks: list) -> str:
        """构建完整 RAG 上下文 (检索 + 长期记忆 + 对话历史)."""
        parts = []

        # 1. 检索到的文档
        if retrieved_chunks:
            chunk_texts = []
            total = 0
            for chunk, score in retrieved_chunks:
                snippet = f"[来源: {chunk.source}, 相关度: {score:.2f}]\n{chunk.text}"
                if total + len(snippet) < 12000:
                    chunk_texts.append(snippet)
                    total += len(snippet)
            if chunk_texts:
                parts.append("## 📄 相关知识 (从文档中检索)\n\n" + "\n\n---\n\n".join(chunk_texts))

        # 2. 长期记忆
        ltm_context = await self.long_term.build_context_text()
        if ltm_context:
            parts.append(ltm_context)

        return "\n\n".join(parts)
