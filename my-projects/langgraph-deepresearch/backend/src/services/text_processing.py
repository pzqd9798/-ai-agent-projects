"""文本处理工具 — 规范化 Agent 生成的文本, 移除工具调用标记."""

from __future__ import annotations

import re


def strip_tool_calls(text: str) -> str:
    """移除文本中的工具调用标记。"""

    if not text:
        return text

    pattern = re.compile(r"\[TOOL_CALL:[^\]]+\]")
    return pattern.sub("", text)

