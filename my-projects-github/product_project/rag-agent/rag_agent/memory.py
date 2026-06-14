"""双记忆系统 — 短期对话流 + 长期知识库.

短期记忆: 滑动窗口保留最近 N 轮对话
长期记忆: 向量存储 + 用户偏好管理器
"""

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationTurn:
    role: str          # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


# ---------------------------------------------------------------------------
# 短期记忆
# ---------------------------------------------------------------------------

class ShortTermMemory:
    """短期对话记忆 — 滑动窗口."""

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
        """转为 Anthropic API 格式的消息列表."""
        return [{"role": t.role, "content": t.content} for t in self._turns]

    def clear(self) -> None:
        self._turns.clear()

    def __len__(self) -> int:
        return len(self._turns)


# ---------------------------------------------------------------------------
# 长期记忆
# ---------------------------------------------------------------------------

class LongTermMemory:
    """长期记忆 — 用户偏好、关键事实、历史摘要.

    作为独立的键值存储，与向量知识库分离.
    向量存储用于文档检索，这个用于用户相关的记忆.
    """

    def __init__(self):
        self._preferences: dict[str, str] = {}    # key -> value
        self._facts: list[str] = []               # 用户提到的事实
        self._session_summaries: list[str] = []   # 往次会话摘要

    # ---- 偏好 ----
    def set_preference(self, key: str, value: str) -> None:
        self._preferences[key] = value

    def get_preference(self, key: str) -> str | None:
        return self._preferences.get(key)

    def all_preferences(self) -> dict[str, str]:
        return dict(self._preferences)

    # ---- 事实 ----
    def add_fact(self, fact: str) -> None:
        if fact not in self._facts:
            self._facts.append(fact)

    def get_facts(self) -> list[str]:
        return list(self._facts)

    # ---- 会话摘要 ----
    def add_session_summary(self, summary: str) -> None:
        self._session_summaries.append(summary)

    def get_recent_summaries(self, limit: int = 5) -> list[str]:
        return self._session_summaries[-limit:]

    # ---- 构建上下文文本 ----
    def build_context_text(self) -> str:
        """构建可注入 LLM 提示词的长期记忆文本."""
        parts = []

        if self._preferences:
            parts.append("## 用户偏好\n" + "\n".join(
                f"- {k}: {v}" for k, v in self._preferences.items()
            ))

        if self._facts:
            parts.append("## 用户相关事实\n" + "\n".join(
                f"- {f}" for f in self._facts
            ))

        if self._session_summaries:
            parts.append("## 历史会话摘要\n" + "\n".join(
                f"- {s}" for s in self._session_summaries[-5:]
            ))

        return "\n\n".join(parts) if parts else ""

    # ---- 持久化 ----
    def save(self, filepath: str) -> None:
        import json
        data = {
            "preferences": self._preferences,
            "facts": self._facts,
            "session_summaries": self._session_summaries,
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, filepath: str) -> None:
        import json
        from pathlib import Path
        if not Path(filepath).exists():
            return
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._preferences = data.get("preferences", {})
        self._facts = data.get("facts", [])
        self._session_summaries = data.get("session_summaries", [])


# ---------------------------------------------------------------------------
# 记忆管理器
# ---------------------------------------------------------------------------

class MemoryManager:
    """统一管理短期 + 长期记忆."""

    def __init__(self):
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory()

    def add_user_message(self, content: str) -> None:
        self.short_term.add("user", content)

    def add_assistant_message(self, content: str) -> None:
        self.short_term.add("assistant", content)

    def build_rag_context(self, query: str, retrieved_chunks: list,
                          max_chunk_tokens: int = 3000) -> str:
        """构建 RAG 增强的上下文 (知识检索 + 记忆).

        优先级: 检索到的文档 > 用户偏好 > 历史事实 > 历史会话
        """
        parts = []

        # 1. 检索到的文档片段
        if retrieved_chunks:
            chunk_texts = []
            total = 0
            for chunk, score in retrieved_chunks:
                snippet = f"[来源: {chunk.source}, 相关度: {score:.2f}]\n{chunk.text}"
                if total + len(snippet) < max_chunk_tokens * 4:
                    chunk_texts.append(snippet)
                    total += len(snippet)
            if chunk_texts:
                parts.append("## 📄 相关知识 (从文档中检索)\n\n" + "\n\n---\n\n".join(chunk_texts))

        # 2. 长期记忆
        ltm_context = self.long_term.build_context_text()
        if ltm_context:
            parts.append(ltm_context)

        # 3. 对话历史
        recent = self.short_term.get_recent(10)
        if recent:
            parts.append("## 💬 最近对话\n\n" + "\n".join(
                f"**{t.role}**: {t.content[:300]}" for t in recent
            ))

        return "\n\n".join(parts)

    def auto_extract_memory(self, user_message: str, assistant_reply: str) -> None:
        """从对话中自动提取偏好和事实 (简单规则)."""
        # 检测偏好表达: "我喜欢X", "我常用Y"
        import re
        pref_patterns = [
            r"我(喜欢|偏爱|常用|习惯用)\s*(.+?)(?:[。，,;]|$)",
            r"我(是|做|从事)\s*(.+?)(?:[。，,;]|$)",
        ]
        for pattern in pref_patterns:
            for m in re.finditer(pattern, user_message):
                self.long_term.add_fact(m.group(0))

        # 从回复中提取确认的偏好
        if "我记住了" in assistant_reply or "已记住" in assistant_reply:
            self.long_term.add_fact(user_message)
