"""Short-term memory — sliding window research context with key-info retention."""

from __future__ import annotations

from typing import Any


class ShortTermMemory:
    """Manages the active research context window for a single session.

    Maintains a sliding window of recent messages and extracted key facts
    that are always kept regardless of window size constraints.
    """

    def __init__(self, max_messages: int = 20, max_key_facts: int = 10) -> None:
        self.max_messages = max_messages
        self.max_key_facts = max_key_facts
        self._messages: list[dict[str, Any]] = []
        self._key_facts: list[str] = []

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})
        if len(self._messages) > self.max_messages:
            # Keep most recent
            self._messages = self._messages[-self.max_messages :]

    def add_key_fact(self, fact: str) -> None:
        """Store a key finding that should always be included in context."""
        if fact not in self._key_facts:
            self._key_facts.append(fact)
        if len(self._key_facts) > self.max_key_facts:
            self._key_facts = self._key_facts[-self.max_key_facts :]

    def get_messages(self) -> list[dict[str, Any]]:
        return list(self._messages)

    def get_key_facts(self) -> list[str]:
        return list(self._key_facts)

    def build_context_text(self) -> str:
        """Build a compact context string for prompts."""
        parts: list[str] = []
        if self._key_facts:
            parts.append("## 关键发现\n")
            for i, fact in enumerate(self._key_facts, 1):
                parts.append(f"{i}. {fact}")
            parts.append("")
        if self._messages:
            parts.append("## 近期对话\n")
            for msg in self._messages[-6:]:
                role = msg["role"]
                content = str(msg.get("content", ""))[:500]
                parts.append(f"**{role}**: {content}")
        return "\n".join(parts)

    def clear(self) -> None:
        self._messages.clear()
        self._key_facts.clear()

    def __len__(self) -> int:
        return len(self._messages)
