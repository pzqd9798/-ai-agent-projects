"""上下文溢出保护 — 3 阶段重试洋葱.

基于 claw0 s03 ContextGuard, 当 LLM 上下文窗口溢出时:
    1. 截断过大的工具结果
    2. 用 LLM 摘要压缩历史消息
    3. 仍溢出则抛出异常
"""

import json
from anthropic import Anthropic

from app.config import config


class ContextGuard:
    """保护 Agent 免受上下文窗口溢出."""

    def __init__(self, max_tokens: int | None = None):
        self.max_tokens = max_tokens or config.session.context_safe_limit

    # ------------------------------------------------------------------
    # Token 估算 (启发式: len(text) // 4)
    # ------------------------------------------------------------------

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return len(text) // 4

    def estimate_messages_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += self.estimate_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        if "text" in block:
                            total += self.estimate_tokens(block["text"])
                        elif block.get("type") == "tool_result":
                            rc = block.get("content", "")
                            if isinstance(rc, str):
                                total += self.estimate_tokens(rc)
                        elif block.get("type") == "tool_use":
                            total += self.estimate_tokens(json.dumps(block.get("input", {})))
        return total

    # ------------------------------------------------------------------
    # 阶段 1: 截断过大的工具结果
    # ------------------------------------------------------------------

    def truncate_tool_result(self, result: str, max_fraction: float = 0.3) -> str:
        max_chars = int(self.max_tokens * 4 * max_fraction)
        if len(result) <= max_chars:
            return result
        cut = result.rfind("\n", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        head = result[:cut]
        return head + f"\n\n[... 已截断 ({len(result)} 字符, 显示前 {len(head)} 字符) ...]"

    def _truncate_large_tool_results(self, messages: list[dict]) -> list[dict]:
        result = []
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                new_blocks = []
                for block in content:
                    if (isinstance(block, dict)
                            and block.get("type") == "tool_result"
                            and isinstance(block.get("content"), str)):
                        block = dict(block)
                        block["content"] = self.truncate_tool_result(block["content"])
                    new_blocks.append(block)
                result.append({"role": msg["role"], "content": new_blocks})
            else:
                result.append(msg)
        return result

    # ------------------------------------------------------------------
    # 阶段 2: LLM 摘要压缩
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize_for_summary(messages: list[dict]) -> str:
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg.get("content", "")
            if isinstance(content, str):
                parts.append(f"[{role}]: {content}")
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        t = block.get("type", "")
                        if t == "text":
                            parts.append(f"[{role}]: {block['text']}")
                        elif t == "tool_use":
                            parts.append(f"[{role} called {block.get('name', '?')}]")
                        elif t == "tool_result":
                            rc = block.get("content", "")
                            preview = rc[:300] if isinstance(rc, str) else str(rc)[:300]
                            parts.append(f"[tool_result]: {preview}")
        return "\n".join(parts)

    def compact_history(self, messages: list[dict],
                        api_client: Anthropic, model: str) -> list[dict]:
        """将前 50% 的消息压缩为 LLM 摘要."""
        total = len(messages)
        if total <= 4:
            return messages

        keep_count = max(4, int(total * 0.2))
        compress_count = max(2, int(total * 0.5))
        compress_count = min(compress_count, total - keep_count)
        if compress_count < 2:
            return messages

        old_messages = messages[:compress_count]
        recent_messages = messages[compress_count:]

        old_text = self._serialize_for_summary(old_messages)
        summary_prompt = (
            "简要总结以下对话，保留关键事实和决策。只输出摘要，不要前言。\n\n" + old_text
        )

        try:
            resp = api_client.messages.create(
                model=model, max_tokens=2048,
                system="你是一个对话摘要器。简洁、实事求是。",
                messages=[{"role": "user", "content": summary_prompt}],
            )
            summary_text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    summary_text += block.text
        except Exception:
            return recent_messages

        return [
            {"role": "user", "content": "[历史对话摘要]\n" + summary_text},
            {"role": "assistant", "content": [{"type": "text", "text": "已理解，我有了上下文。"}]},
        ] + recent_messages

    # ------------------------------------------------------------------
    # 主入口: 带保护的 API 调用
    # ------------------------------------------------------------------

    def guard_api_call(
        self,
        api_client: Anthropic,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_retries: int = 2,
    ):
        """三阶段重试包装器."""
        current = messages

        for attempt in range(max_retries + 1):
            try:
                kwargs: dict = {
                    "model": model, "max_tokens": 8096,
                    "system": system, "messages": current,
                }
                if tools:
                    kwargs["tools"] = tools

                result = api_client.messages.create(**kwargs)

                # 成功 — 如果替换过 messages，回写
                if current is not messages:
                    messages.clear()
                    messages.extend(current)
                return result

            except Exception as exc:
                error_str = str(exc).lower()
                is_overflow = ("context" in error_str or "token" in error_str)

                if not is_overflow or attempt >= max_retries:
                    raise

                if attempt == 0:
                    print("  [guard] 上下文溢出，截断大工具结果...")
                    current = self._truncate_large_tool_results(current)
                elif attempt == 1:
                    print("  [guard] 仍然溢出，压缩历史...")
                    current = self.compact_history(current, api_client, model)

        raise RuntimeError("guard_api_call: 重试耗尽")
