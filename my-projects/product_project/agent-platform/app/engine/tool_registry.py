"""工具注册表 — TOOLS schema + TOOL_HANDLERS 分发表.

核心认知 (来自 claw0 s02):
    TOOLS 数组 = 告诉模型 "你可以用哪些工具"
    TOOL_HANDLERS 字典 = 告诉代码 "收到工具调用时执行什么函数"
    两者通过 name 字段关联.
"""

from typing import Any, Callable

from app.config import config

# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------

# TOOLS: 传给 LLM 的 schema 数组
TOOLS: list[dict] = []

# TOOL_HANDLERS: tool_name -> handler 函数
TOOL_HANDLERS: dict[str, Callable[..., str]] = {}

# 工具元数据
TOOL_META: dict[str, dict] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: dict,
    handler: Callable[..., str],
    dangerous: bool = False,
) -> None:
    """注册一个工具."""
    TOOLS.append({
        "name": name,
        "description": description,
        "input_schema": input_schema,
    })
    TOOL_HANDLERS[name] = handler
    TOOL_META[name] = {
        "description": description,
        "dangerous": dangerous,
    }


# ---------------------------------------------------------------------------
# 工具分发
# ---------------------------------------------------------------------------


def process_tool_call(tool_name: str, tool_input: dict) -> str:
    """根据工具名分发到对应的处理函数.

    这是整个 Agent 核心调度逻辑 — 和 claw0 s02 完全相同.
    错误以字符串返回 (而非抛出异常), 让 LLM 可以看到错误并自我修正.
    """
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return f"Error: Unknown tool '{tool_name}'"

    try:
        return handler(**tool_input)
    except TypeError as exc:
        return f"Error: Invalid arguments for {tool_name}: {exc}"
    except Exception as exc:
        return f"Error: {tool_name} failed: {exc}"
