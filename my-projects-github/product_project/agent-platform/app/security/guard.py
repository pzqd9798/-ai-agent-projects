"""安全护栏 — 输入/输出/工具三层防护."""

import re


# ---------------------------------------------------------------------------
# 输入护栏: Prompt 注入检测
# ---------------------------------------------------------------------------

# 已知注入模式
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions?|prompts?)",
    r"你.*是.*新的.*(角色|AI|assistant)",
    r"forget\s+(everything|all)",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"\[system\]",
    r"DAN\s*mode",
]


def scan_input(text: str) -> dict:
    """扫描用户输入, 检测 Prompt 注入攻击.

    Returns:
        {"safe": bool, "score": float, "reasons": list[str]}
        score 0.0 = 安全, 1.0 = 确定攻击
    """
    text_lower = text.lower()
    reasons = []

    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            reasons.append(f"匹配注入模式: {pattern}")

    # 检测过长的系统指令风格文本
    if len(text) > 500 and ("你必须" in text or "你的角色是" in text):
        reasons.append("包含系统指令风格的超长文本")

    score = min(1.0, len(reasons) * 0.6)
    return {
        "safe": score < 0.3,
        "score": score,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# 输出护栏: 敏感信息脱敏
# ---------------------------------------------------------------------------

_SENSITIVE_PATTERNS = [
    (re.compile(r"\b\d{11}\b"), "[手机号]"),          # 11 位手机号
    (re.compile(r"\b\d{6}(19|20)\d{2}(0[1-9]|1[0-2])\d{4}\b"), "[身份证号]"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "[API_KEY]"),
    (re.compile(r"[\w.-]+@[\w.-]+\.\w+"), "[邮箱]"),
    (re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[银行卡号]"),
]


def sanitize_output(text: str) -> tuple[str, list[str]]:
    """脱敏输出中的敏感信息.

    Returns:
        (sanitized_text, list of replaced types)
    """
    replaced = []
    for pattern, label in _SENSITIVE_PATTERNS:
        matches = pattern.findall(text)
        if matches:
            text = pattern.sub(label, text)
            replaced.append(label)
    return text, replaced


# ---------------------------------------------------------------------------
# 工具护栏: 权限控制
# ---------------------------------------------------------------------------

# 高危工具需要确认
_DANGEROUS_TOOLS = {"bash", "write_file"}

# 工具调用频率限制
_tool_call_counts: dict[str, list[float]] = {}  # tool_name -> [timestamps]
_MAX_CALLS_PER_MINUTE = 30


def check_tool_permission(tool_name: str, tool_input: dict,
                          require_approval: bool = False) -> dict:
    """检查工具调用是否被允许.

    Returns:
        {"allowed": bool, "reason": str}
    """
    import time

    # 频率限制
    now = time.time()
    if tool_name not in _tool_call_counts:
        _tool_call_counts[tool_name] = []
    timestamps = _tool_call_counts[tool_name]
    timestamps[:] = [t for t in timestamps if now - t < 60]
    if len(timestamps) >= _MAX_CALLS_PER_MINUTE:
        return {"allowed": False, "reason": f"工具 {tool_name} 调用频率超限"}
    timestamps.append(now)

    # 参数大小限制
    input_str = str(tool_input)
    if len(input_str) > 100_000:
        return {"allowed": False, "reason": f"工具参数过大 ({len(input_str)} 字符)"}

    return {"allowed": True, "reason": "ok"}
