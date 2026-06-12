"""
Debug Logger — 5-level logging system for agent harness debugging.

Levels (from most to least verbose):
    TRACE  — raw API request/response, full tool outputs
    DEBUG  — tool call summary, token usage per step
    INFO   — loop iteration markers, step summaries
    WARN   — recoverable errors, retries, fallback paths
    ERROR  — fatal errors that stop the agent

Usage:
    logger = DebugLogger(level="INFO")   # default for normal use
    logger = DebugLogger(level="DEBUG")  # --debug flag
    logger = DebugLogger(level="TRACE")  # --trace flag
"""

import sys
from datetime import datetime
from typing import Literal

Level = Literal["TRACE", "DEBUG", "INFO", "WARN", "ERROR"]

LEVEL_VALUES = {"TRACE": 0, "DEBUG": 1, "INFO": 2, "WARN": 3, "ERROR": 4}

# ANSI color codes
COLORS = {
    "TRACE": "\033[90m",    # grey
    "DEBUG": "\033[36m",    # cyan
    "INFO":  "\033[32m",    # green
    "WARN":  "\033[33m",    # yellow
    "ERROR": "\033[31m",    # red
    "STEP":  "\033[35m",    # magenta
    "RESET": "\033[0m",
    "BOLD":  "\033[1m",
    "DIM":   "\033[2m",
}


class DebugLogger:
    """5-level hierarchical debug logger with colored output."""

    def __init__(self, level: Level = "INFO", file=None):
        self.level = level
        self.level_value = LEVEL_VALUES[level]
        self.file = file or sys.stderr
        self._step_counter = 0

    def set_level(self, level: Level):
        """Change log level at runtime."""
        self.level = level
        self.level_value = LEVEL_VALUES[level]

    def _log(self, level: Level, prefix: str, msg: str):
        """Internal: emit a log line if the level is >= current threshold."""
        if LEVEL_VALUES[level] < self.level_value:
            return

        color = COLORS.get(level, "")
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"{COLORS['DIM']}{timestamp}{COLORS['RESET']} {color}{prefix:6s}{COLORS['RESET']} {msg}"
        print(line, file=self.file)

    def trace(self, msg: str):
        """Most verbose: raw API payloads, full tool outputs."""
        self._log("TRACE", "TRACE", msg)

    def debug(self, msg: str):
        """Tool call details, token consumption per step, intermediate states."""
        self._log("DEBUG", "DEBUG", msg)

    def info(self, msg: str):
        """Loop iteration markers, task-level progress."""
        self._log("INFO", "INFO", msg)

    def warn(self, msg: str):
        """Recoverable errors: timeouts, blocked commands, retries."""
        self._log("WARN", "WARN", msg)

    def error(self, msg: str):
        """Fatal errors: API failures, max steps exceeded."""
        self._log("ERROR", "ERROR", msg)

    # ── Special formatting helpers ──────────────────────────

    def step(self, n: int, msg: str = ""):
        """Emit a prominent step marker (always shows, regardless of level)."""
        self._step_counter = n
        color = COLORS["STEP"]
        reset = COLORS["RESET"]
        bold = COLORS["BOLD"]
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = (f"{COLORS['DIM']}{timestamp}{reset} "
                f"{color}{bold}◆ STEP {n}{reset}"
                f"{' — ' + msg if msg else ''}")
        print(line, file=self.file)

    def separator(self, char: str = "─", width: int = 60):
        """Print a visual separator."""
        print(f"{COLORS['DIM']}{char * width}{COLORS['RESET']}", file=self.file)

    def banner(self, text: str):
        """Print a highlighted banner."""
        bold = COLORS["BOLD"]
        reset = COLORS["RESET"]
        print(f"\n{bold}{'=' * 60}{reset}", file=self.file)
        print(f"{bold}  {text}{reset}", file=self.file)
        print(f"{bold}{'=' * 60}{reset}\n", file=self.file)

    def tool_call(self, name: str, params: dict, output_preview: str = ""):
        """Log a tool invocation with params and output preview."""
        if self.level_value > LEVEL_VALUES["DEBUG"]:
            return
        color = COLORS["DEBUG"]
        reset = COLORS["RESET"]
        dim = COLORS["DIM"]
        print(f"{dim}  ├─ Tool:{reset} {color}{name}{reset}", file=self.file)
        # Show key params compactly
        key_params = {k: str(v)[:80] for k, v in params.items()}
        print(f"{dim}  │  Params:{reset} {key_params}", file=self.file)
        if output_preview:
            preview = output_preview[:300].replace("\n", "\\n")
            print(f"{dim}  └─ Result:{reset} {preview}", file=self.file)

    def token_usage(self, step: int, input_tokens: int, output_tokens: int):
        """Log token usage for a step."""
        if self.level_value > LEVEL_VALUES["INFO"]:
            return
        self.info(
            f"Step {step} tokens — "
            f"in: {input_tokens:,} | out: {output_tokens:,} | "
            f"total: {input_tokens + output_tokens:,}"
        )
