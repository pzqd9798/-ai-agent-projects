"""
核心 Agent 循环 — 整个脚手架的心脏.

模式 (来自 claw0 s01/s02):
    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        通过分发表执行工具
        将工具结果追加到 messages
        循环

这个循环刻意保持简单 — 所有复杂性都在外围层:
    tools.py   → Agent 能做什么
    logger.py  → 我们如何看到发生了什么
    session.py → 我们如何记住发生了什么

添加工具、钩子或权限时, 循环本身不需要改变.
这就是关键的架构洞察.
"""

import time
from typing import Any

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

from .tools import TOOLS, execute_tool
from .logger import DebugLogger
from .session import Session


def agent_loop(
    messages: list[dict],
    client: Any,
    model: str,
    system_prompt: str,
    logger: DebugLogger,
    session: Session,
    max_steps: int = 30,
):
    """
    The agent loop: call LLM → execute tools → feed results → repeat.

    This is the SAME loop from s01 (30 lines), but instrumented with:
        - Step-by-step debug logging
        - Session recording for later replay
        - Token tracking
        - Max-steps safety limit
        - Graceful error recovery

    Args:
        messages: conversation history (mutated in-place)
        client: Anthropic client instance
        model: model ID string
        system_prompt: system prompt string
        logger: DebugLogger instance
        session: Session instance for recording
        max_steps: safety limit on loop iterations
    """
    step = 0

    while step < max_steps:
        step += 1
        logger.step(step, "Calling model...")
        logger.separator()

        # ── Call LLM ──────────────────────────────────────
        t0 = time.perf_counter()
        try:
            response = client.messages.create(
                model=model,
                system=system_prompt,
                messages=messages,
                tools=TOOLS,
                max_tokens=8000,
            )
        except Exception as e:
            logger.error(f"API call failed: {e}")
            session.errors.append({
                "step": step,
                "tool": "__api__",
                "error": str(e)[:200],
            })
            return  # Fatal: can't recover from API failure in this demo

        elapsed_ms = (time.perf_counter() - t0) * 1000

        # ── Log raw response (trace level) ─────────────────
        logger.trace(f"stop_reason={response.stop_reason} "
                     f"content_blocks={len(response.content)}")

        # ── Track token usage ─────────────────────────────
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        session.record_step(step, tokens_in, tokens_out,
                           response.stop_reason, elapsed_ms)
        logger.token_usage(step, tokens_in, tokens_out)

        # ── Append assistant turn ─────────────────────────
        messages.append({"role": "assistant", "content": response.content})

        # ── Check if model is done ────────────────────────
        if response.stop_reason != "tool_use":
            logger.info(f"Model stopped: {response.stop_reason}")
            logger.separator()
            return

        # ── Execute tools ─────────────────────────────────
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name = block.name
            tool_input = dict(block.input)

            logger.debug(f"Executing: {tool_name}")
            logger.tool_call(tool_name, tool_input)

            t_tool = time.perf_counter()
            result = execute_tool(tool_name, tool_input)
            tool_elapsed = (time.perf_counter() - t_tool) * 1000

            # Record
            session.record_tool_call(step, tool_name, tool_input,
                                     result, tool_elapsed)

            # Log result
            output_preview = str(result.get("output", ""))[:200]
            if result.get("ok"):
                logger.debug(f"  ✓ {tool_name} OK ({tool_elapsed:.0f}ms)")
            else:
                logger.warn(f"  ✗ {tool_name} FAILED: {output_preview[:150]}")

            logger.tool_call(tool_name, tool_input, output_preview)

            # Build tool_result block
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result.get("output", str(result)),
            })

        # ── Feed tool results back to model ────────────────
        messages.append({"role": "user", "content": tool_results})
        logger.info(f"Step {step} complete — {len(tool_results)} tool(s) executed")

    # ── Max steps exceeded ──────────────────────────────────
    logger.warn(f"MAX STEPS ({max_steps}) reached — forcing stop. "
                f"Session recorded {session.steps} steps, "
                f"{len(session.tool_calls)} tool calls.")
