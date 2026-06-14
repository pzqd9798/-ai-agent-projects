"""Prompt injection detection and input sanitization."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Injection patterns
# ---------------------------------------------------------------------------

_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions?", "指令覆盖"),
    (r"forget\s+(all\s+)?(your|the)\s+(instructions|prompt|rules)", "指令遗忘"),
    (r"you\s+are\s+now\s+(DAN|STAN|jailbroken)", "角色越狱"),
    (r"system\s*:\s*.*new\s+prompt", "系统提示覆盖"),
    (r"<\|im_start\|>", "特殊令牌注入"),
    (r"\[SYSTEM\].*\[/SYSTEM\]", "系统标签注入"),
    (r"prompt\s*=\s*[\"'].*[\"']", "提示词赋值"),
    (r"role\s*:\s*system", "角色伪装"),
]

SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r'sk-[a-zA-Z0-9]{32,}', "OpenAI API Key"),
    (r'tvly-[a-zA-Z0-9\-]{20,}', "Tavily API Key"),
    (r'pplx-[a-zA-Z0-9\-]{20,}', "Perplexity API Key"),
    (r'github_pat_[a-zA-Z0-9_]{20,}', "GitHub PAT"),
    (r'eyJ[a-zA-Z0-9\-_]+\.eyJ[a-zA-Z0-9\-_]+\.', "JWT Token"),
]


@dataclass
class GuardResult:
    safe: bool = True
    reason: str = ""
    sanitized: str = ""


class InputGuard:
    """Rule-based prompt injection detection."""

    def __init__(self, *, strip_sensitive: bool = True) -> None:
        self.strip_sensitive = strip_sensitive

    def check(self, text: str) -> GuardResult:
        """Detect injection attempts in user input."""
        lower = text.lower()
        for pattern, label in _INJECTION_PATTERNS:
            if re.search(pattern, lower, re.IGNORECASE):
                return GuardResult(
                    safe=False,
                    reason=f"检测到潜在的提示注入: {label}",
                    sanitized="",
                )

        sanitized = text
        found_sensitive: list[str] = []
        if self.strip_sensitive:
            for pattern, label in SENSITIVE_PATTERNS:
                if re.search(pattern, sanitized):
                    sanitized = re.sub(pattern, f"[REDACTED:{label}]", sanitized)
                    found_sensitive.append(label)

        if found_sensitive:
            return GuardResult(
                safe=True,
                reason=f"已脱敏: {', '.join(found_sensitive)}",
                sanitized=sanitized,
            )

        return GuardResult(safe=True, sanitized=text)


# Singleton
_guard = InputGuard()


def sanitize_input(text: str) -> GuardResult:
    """Quick sanitization for API endpoints."""
    return _guard.check(text)
