"""基于文本工具调用的简易 Agent, 替代 hello-agents 的 ToolAwareSimpleAgent.

底层使用 LangChain ChatOpenAI, 支持同步和异步模式.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, AsyncIterator, Callable, Iterator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

TOOL_CALL_PATTERN = re.compile(
    r"\[TOOL_CALL:(?P<tool>[^:]+):(?P<body>[^\]]+)\]",
    re.IGNORECASE,
)
TOOL_CALL_START = re.compile(r"\[TOOL_CALL:(?P<tool>[^:]+):", re.IGNORECASE)


class SimpleAgent:
    """Lightweight agent that intercepts [TOOL_CALL:tool:params] markers in LLM output,
    executes the corresponding tools, and feeds results back in a multi-turn loop.

    Designed as a drop-in replacement for hello-agents' ToolAwareSimpleAgent.
    """

    def __init__(
        self,
        *,
        name: str,
        llm: ChatOpenAI,
        system_prompt: str,
        tools: dict[str, Callable[[dict[str, Any]], str]] | None = None,
        tool_call_listener: Callable[[dict[str, Any]], None] | None = None,
        max_turns: int = 5,
    ) -> None:
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.tools: dict[str, Callable[[dict[str, Any]], str]] = tools or {}
        self.listener = tool_call_listener
        self.max_turns = max_turns

    # ------------------------------------------------------------------
    # Sync API
    # ------------------------------------------------------------------

    def run(self, user_prompt: str) -> str:
        """Execute agent synchronously, handling tool calls automatically."""
        messages: list = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for _turn in range(self.max_turns):
            response = self.llm.invoke(messages)
            text = self._extract_text(response)

            tool_calls = self._parse_tool_calls(text)
            if not tool_calls:
                return text

            tool_results = self._execute_all(tool_calls)
            if not tool_results:
                return text

            messages.append(AIMessage(content=text))
            messages.append(HumanMessage(
                content="工具执行结果：\n" + "\n".join(tool_results)
                + "\n请基于以上工具执行结果继续你的工作。"
            ))

        return text

    def stream_run(self, user_prompt: str) -> Iterator[str]:
        """Stream agent output. Handles tool calls in non-streaming passes, then
        streams the final response."""
        messages: list = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for _turn in range(self.max_turns):
            response = self.llm.invoke(messages)
            text = self._extract_text(response)

            tool_calls = self._parse_tool_calls(text)
            if not tool_calls:
                # No more tool calls — stream final pass
                for chunk in self.llm.stream(messages):
                    content = self._extract_text(chunk)
                    if content:
                        yield content
                return

            tool_results = self._execute_all(tool_calls)
            messages.append(AIMessage(content=text))
            messages.append(HumanMessage(
                content="工具执行结果：\n" + "\n".join(tool_results)
                + "\n请基于以上工具执行结果继续你的工作。"
            ))

        # Max turns reached — stream whatever we have
        for chunk in self.llm.stream(messages):
            content = self._extract_text(chunk)
            if content:
                yield content

    def clear_history(self) -> None:
        """Reset agent state (SimpleAgent is stateless — no-op)."""
        pass

    # ------------------------------------------------------------------
    # Async API
    # ------------------------------------------------------------------

    async def arun(self, user_prompt: str) -> str:
        """Async version of run()."""
        messages: list = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for _turn in range(self.max_turns):
            response = await self.llm.ainvoke(messages)
            text = self._extract_text(response)

            tool_calls = self._parse_tool_calls(text)
            if not tool_calls:
                return text

            tool_results = self._execute_all(tool_calls)
            if not tool_results:
                return text

            messages.append(AIMessage(content=text))
            messages.append(HumanMessage(
                content="工具执行结果：\n" + "\n".join(tool_results)
                + "\n请基于以上工具执行结果继续你的工作。"
            ))

        return text

    async def astream_run(self, user_prompt: str) -> AsyncIterator[str]:
        """Async streaming version."""
        messages: list = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]

        for _turn in range(self.max_turns):
            response = await self.llm.ainvoke(messages)
            text = self._extract_text(response)

            tool_calls = self._parse_tool_calls(text)
            if not tool_calls:
                async for chunk in self.llm.astream(messages):
                    content = self._extract_text(chunk)
                    if content:
                        yield content
                return

            tool_results = self._execute_all(tool_calls)
            messages.append(AIMessage(content=text))
            messages.append(HumanMessage(
                content="工具执行结果：\n" + "\n".join(tool_results)
                + "\n请基于以上工具执行结果继续你的工作。"
            ))

        async for chunk in self.llm.astream(messages):
            content = self._extract_text(chunk)
            if content:
                yield content

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _parse_tool_calls(self, text: str) -> list[tuple[str, str]]:
        """Extract (tool_name, params_body) pairs from text.

        Uses bracket-counting to correctly handle nested JSON objects/arrays.
        """
        results: list[tuple[str, str]] = []
        pos = 0

        while True:
            m = TOOL_CALL_START.search(text, pos)
            if not m:
                break

            tool_name = m.group("tool")
            body_start = m.end()
            bracket_depth = 0
            in_string = False
            escape_next = False
            body_end = body_start

            for i in range(body_start, len(text)):
                ch = text[i]

                if escape_next:
                    escape_next = False
                    continue

                if ch == "\\":
                    escape_next = True
                    continue

                if ch == '"' and not escape_next:
                    in_string = not in_string
                    continue

                if in_string:
                    continue

                if ch in ("{", "["):
                    bracket_depth += 1
                elif ch in ("}", "]"):
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        body_end = i + 1
                        break

            if bracket_depth == 0:
                body = text[body_start:body_end]
                results.append((tool_name, body))
                pos = body_end + 1  # skip past closing ]
                if pos < len(text) and text[body_end:body_end + 1] == "]":
                    pass  # consume implicit ] after the JSON body
            else:
                # Fallback to old regex for unmatched brackets
                pos = m.end()

        return results

    def _execute_all(self, tool_calls: list[tuple[str, str]]) -> list[str]:
        """Execute all parsed tool calls, returning result strings."""
        results: list[str] = []
        for tool_name, params_str in tool_calls:
            result = self._execute_one(tool_name, params_str)
            if result:
                results.append(f"[{tool_name}] {result}")
        return results

    def _execute_one(self, tool_name: str, params_str: str) -> str:
        """Execute a single tool call and notify listener."""
        try:
            params = json.loads(params_str)
        except json.JSONDecodeError:
            logger.warning("Failed to parse tool params: %s", params_str[:100])
            return ""

        if tool_name not in self.tools:
            logger.warning("Unknown tool: %s", tool_name)
            return ""

        try:
            result = self.tools[tool_name](params)
            result_str = str(result)
        except Exception:
            logger.exception("Tool %s execution failed", tool_name)
            result_str = "❌ 工具执行失败"

        if self.listener:
            try:
                self.listener({
                    "agent_name": self.name,
                    "tool_name": tool_name,
                    "raw_parameters": params_str,
                    "parsed_parameters": params,
                    "result": result_str,
                })
            except Exception:
                pass

        return result_str

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Extract text content from a LangChain message or chunk."""
        if hasattr(response, "content"):
            content = response.content
            # content might be a string or list of dicts
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return "".join(
                    item.get("text", "") if isinstance(item, dict) else str(item)
                    for item in content
                )
        return str(response)
