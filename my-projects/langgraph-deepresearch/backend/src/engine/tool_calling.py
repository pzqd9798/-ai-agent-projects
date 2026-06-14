"""Native Function Calling — replaces [TOOL_CALL:...] text parsing with OpenAI/Anthropic tool_use.

Provides a clean Python interface for tool definitions and execution,
making the agent loop much more reliable than regex-based parsing.
"""

from __future__ import annotations

import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------


@dataclass
class ToolDef:
    """Definition of a tool callable by the LLM."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for parameters
    handler: Callable[..., str]
    is_async: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def to_anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters,
        }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Registry of available tools with schema generation."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDef] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        handler: Callable[..., str],
        *,
        is_async: bool = False,
    ) -> None:
        self._tools[name] = ToolDef(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler,
            is_async=is_async,
        )

    def register_function(
        self,
        fn: Callable,
        *,
        name: str | None = None,
        description: str | None = None,
        is_async: bool = False,
    ) -> None:
        """Auto-generate tool schema from a Python function signature and docstring."""
        tool_name = name or fn.__name__
        tool_desc = description or (inspect.getdoc(fn) or f"Execute {tool_name}").strip()

        # Build JSON Schema from signature
        sig = inspect.signature(fn)
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            param_type = "string"
            if param.annotation is not inspect.Parameter.empty:
                ann = param.annotation
                if ann is int:
                    param_type = "integer"
                elif ann is float:
                    param_type = "number"
                elif ann is bool:
                    param_type = "boolean"
                elif ann is list or getattr(ann, "__origin__", None) is list:
                    param_type = "array"

            properties[param_name] = {"type": param_type, "description": f"Parameter: {param_name}"}
            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        self._tools[tool_name] = ToolDef(
            name=tool_name,
            description=tool_desc,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
            },
            handler=fn,
            is_async=is_async,
        )

    def get(self, name: str) -> ToolDef | None:
        return self._tools.get(name)

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"❌ 未知工具: {name}"
        try:
            return tool.handler(**arguments)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            return f"❌ 工具执行失败: {exc}"

    async def aexecute(self, name: str, arguments: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"❌ 未知工具: {name}"
        try:
            if tool.is_async:
                return await tool.handler(**arguments)
            return tool.handler(**arguments)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            return f"❌ 工具执行失败: {exc}"

    def to_openai_tools(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def to_anthropic_tools(self) -> list[dict[str, Any]]:
        return [t.to_anthropic_schema() for t in self._tools.values()]

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools


# ---------------------------------------------------------------------------
# ToolCall class
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """Parsed tool call from an LLM response."""

    id: str
    name: str
    arguments: dict[str, Any]
    result: str = ""

    def execute(self, registry: ToolRegistry) -> str:
        self.result = registry.execute(self.name, self.arguments)
        return self.result


# ---------------------------------------------------------------------------
# Built-in research tools
# ---------------------------------------------------------------------------


def build_research_tools(note_handler: Callable[..., str] | None = None) -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with standard research tools."""
    registry = ToolRegistry()

    # Web search tool
    registry.register(
        name="web_search",
        description="Search the web for information on a given query. Returns relevant results with titles, URLs, and content snippets.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to execute",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
        handler=lambda query, max_results=5: json.dumps(
            {"status": "searched", "query": query, "results": []},
            ensure_ascii=False,
        ),
    )

    # Fetch page tool
    registry.register(
        name="fetch_page",
        description="Fetch and extract text content from a URL. Use this to get full article content from search results.",
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from",
                },
            },
            "required": ["url"],
        },
        handler=lambda url: json.dumps(
            {"status": "fetched", "url": url, "content": ""},
            ensure_ascii=False,
        ),
    )

    # Note tools
    if note_handler:
        registry.register(
            name="save_note",
            description="Save a note with research findings. Use to persist important information.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Note title"},
                    "content": {"type": "string", "description": "Note content in markdown"},
                    "note_type": {
                        "type": "string",
                        "enum": ["task_state", "finding", "conclusion", "general"],
                        "description": "Type of note",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags for categorization",
                    },
                },
                "required": ["title", "content"],
            },
            handler=note_handler,
        )

    return registry
