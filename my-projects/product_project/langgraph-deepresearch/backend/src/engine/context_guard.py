"""Context guard — 3-stage overflow protection for LLM context windows."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Rough estimate: 4 characters ≈ 1 token
CHARS_PER_TOKEN = 4


class ContextGuard:
    """Manages context window overflow with 3-stage retry strategy:
    1. Truncate oldest messages (keep system + last N)
    2. Compress via LLM summarization of removed messages
    3. Error if still over limit
    """

    def __init__(
        self,
        max_tokens: int = 100_000,
        reserve_tokens: int = 8_000,  # Reserve for response
        min_messages: int = 2,  # Always keep at least system + latest user
    ) -> None:
        self.max_tokens = max_tokens
        self.reserve_tokens = reserve_tokens
        self.min_messages = min_messages
        self.effective_limit = max_tokens - reserve_tokens

    def estimate_tokens(self, text: str) -> int:
        """Rough token count estimation."""
        return max(1, len(text) // CHARS_PER_TOKEN)

    def estimate_messages_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Estimate total tokens across all messages."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total += self.estimate_tokens(str(block.get("text", "")))
        return total

    def stage1_truncate(
        self,
        messages: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        """Stage 1: Truncate oldest non-system messages to fit context.
        Returns (truncated_messages, was_truncated).
        """
        if not messages:
            return messages, False

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        current_tokens = self.estimate_messages_tokens(messages)
        if current_tokens <= self.effective_limit:
            return messages, False

        # Keep removing oldest non-system messages
        while len(non_system) > self.min_messages:
            removed = non_system.pop(0)
            current_tokens -= self.estimate_tokens(str(removed.get("content", "")))
            if current_tokens <= self.effective_limit:
                break

        truncated = system_msgs + non_system
        was_truncated = len(truncated) < len(messages)
        if was_truncated:
            logger.info(
                "ContextGuard stage1: truncated %d → %d messages (%d tokens)",
                len(messages), len(truncated),
                self.estimate_messages_tokens(truncated),
            )
        return truncated, was_truncated

    def check_overflow(self, messages: list[dict[str, Any]]) -> int:
        """Return overflow token count (0 if within limits)."""
        current = self.estimate_messages_tokens(messages)
        overflow = current - self.effective_limit
        return max(0, overflow)
