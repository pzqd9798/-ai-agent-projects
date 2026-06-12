"""
Session Recorder — captures everything that happens in an agent run.

Records:
    - All messages (user + assistant + tool results)
    - Tool calls with inputs/outputs
    - Token usage per step
    - Timing information

Supports:
    - Real-time stats via :stats command
    - Auto-save to transcripts/ on exit
    - Manual save via :save command
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


class Session:
    """Records a complete agent conversation for replay and analysis."""

    def __init__(self, save_dir: str = "transcripts"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        self.start_time = time.time()
        self.steps = 0
        self.total_tokens_in = 0
        self.total_tokens_out = 0

        # Detailed records
        self.tool_calls: list[dict] = []   # [{step, tool, params, result, ok, elapsed_ms}]
        self.step_log: list[dict] = []     # [{step, tokens_in, tokens_out, stop_reason, elapsed_ms}]
        self.errors: list[dict] = []       # [{step, tool, error_msg}]

        # Full message history (for replay)
        self.messages: list[dict] = []

        # User queries for the transcript header
        self.user_queries: list[str] = []

    # ── Recording ─────────────────────────────────────────

    def add_user_query(self, query: str):
        """Record a user query."""
        self.user_queries.append(query)

    def record_step(self, step: int, tokens_in: int, tokens_out: int,
                    stop_reason: str, elapsed_ms: float):
        """Record one loop iteration."""
        self.steps = step
        self.total_tokens_in += tokens_in
        self.total_tokens_out += tokens_out
        self.step_log.append({
            "step": step,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "stop_reason": stop_reason,
            "elapsed_ms": round(elapsed_ms, 1),
        })

    def record_tool_call(self, step: int, tool_name: str, params: dict,
                         result: dict, elapsed_ms: float):
        """Record a single tool execution."""
        ok = result.get("ok", False)
        output_preview = str(result.get("output", ""))[:200]

        self.tool_calls.append({
            "step": step,
            "tool": tool_name,
            "params": {k: str(v)[:100] for k, v in params.items()},
            "ok": ok,
            "output_preview": output_preview,
            "elapsed_ms": round(elapsed_ms, 1),
        })

        if not ok:
            self.errors.append({
                "step": step,
                "tool": tool_name,
                "error": output_preview,
            })

    def record_messages(self, messages: list):
        """Save a snapshot of the full message array."""
        self.messages = messages

    # ── Statistics ────────────────────────────────────────

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def success_rate(self) -> float:
        if not self.tool_calls:
            return 1.0
        ok_count = sum(1 for tc in self.tool_calls if tc["ok"])
        return ok_count / len(self.tool_calls)

    def summary(self) -> str:
        """Return a formatted session summary string."""
        elapsed = self.elapsed_seconds
        if elapsed < 60:
            time_str = f"{elapsed:.1f}s"
        else:
            time_str = f"{elapsed / 60:.1f}min"

        lines = [
            "",
            "=" * 50,
            "  [Session Summary]",
            "=" * 50,
            f"  Steps:           {self.steps}",
            f"  Duration:        {time_str}",
            f"  Tool calls:      {len(self.tool_calls)}",
            f"  Errors:          {self.error_count}",
            f"  Tool success:    {self.success_rate:.0%}",
            f"  Tokens in:       {self.total_tokens_in:,}",
            f"  Tokens out:      {self.total_tokens_out:,}",
            f"  Total tokens:    {self.total_tokens_in + self.total_tokens_out:,}",
            "-" * 50,
        ]

        if self.tool_calls:
            lines.append("  Tool call breakdown:")
            tool_counts = {}
            for tc in self.tool_calls:
                name = tc["tool"]
                tool_counts[name] = tool_counts.get(name, 0) + 1
            for name, count in sorted(tool_counts.items()):
                lines.append(f"    {name}: {count}x")

        if self.errors:
            lines.append("-" * 50)
            lines.append("  Errors encountered:")
            for err in self.errors:
                lines.append(f"    Step {err['step']} [{err['tool']}]: {err['error'][:100]}")

        lines.append("=" * 50)
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────

    def save(self, filename: str | None = None) -> Path:
        """
        Save the full session as a Markdown transcript.
        Returns the path to the saved file.
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"session_{timestamp}.md"

        filepath = self.save_dir / filename

        # Build transcript
        lines = []
        lines.append(f"# Agent Harness Session Transcript")
        lines.append(f"")
        lines.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"**Duration:** {self.elapsed_seconds:.1f}s")
        lines.append(f"**Steps:** {self.steps}")
        lines.append(f"**Tool calls:** {len(self.tool_calls)}")
        lines.append(f"**Tokens:** {self.total_tokens_in:,} in / {self.total_tokens_out:,} out")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

        # User queries
        lines.append(f"## User Queries")
        for i, q in enumerate(self.user_queries, 1):
            lines.append(f"{i}. `{q}`")
        lines.append(f"")

        # Step-by-step log
        lines.append(f"## Step Log")
        lines.append(f"")
        lines.append(f"| Step | Tokens In | Tokens Out | Stop Reason | Time |")
        lines.append(f"|------|-----------|------------|-------------|------|")
        for entry in self.step_log:
            lines.append(
                f"| {entry['step']} | {entry['tokens_in']:,} | "
                f"{entry['tokens_out']:,} | {entry['stop_reason']} | "
                f"{entry['elapsed_ms']:.0f}ms |"
            )
        lines.append(f"")

        # Tool calls
        lines.append(f"## Tool Calls")
        lines.append(f"")
        for tc in self.tool_calls:
            status = "✅" if tc["ok"] else "❌"
            lines.append(f"### Step {tc['step']}: {status} `{tc['tool']}`")
            lines.append(f"```")
            lines.append(f"Params: {json.dumps(tc['params'], ensure_ascii=False, indent=2)}")
            lines.append(f"Output: {tc['output_preview']}")
            lines.append(f"Time:   {tc['elapsed_ms']:.0f}ms")
            lines.append(f"```")
            lines.append(f"")

        # Errors
        if self.errors:
            lines.append(f"## Errors")
            lines.append(f"")
            for err in self.errors:
                lines.append(f"- **Step {err['step']}** `{err['tool']}`: {err['error']}")
            lines.append(f"")

        lines.append(f"---")
        lines.append(f"*Generated by agent-harness-demo*")

        content = "\n".join(lines)
        filepath.write_text(content, encoding="utf-8")
        return filepath
