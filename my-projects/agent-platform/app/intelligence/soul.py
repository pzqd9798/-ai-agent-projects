"""智能层 — 人格/系统提示词组装.

基于 claw0 s06: 系统提示词从磁盘文件组装, 换文件就换人格, 不用改代码.
"""

from pathlib import Path

# 提示词片段目录
PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "workspace" / "prompts"


def load_prompt_file(filename: str) -> str:
    """从 workspace/prompts/ 加载提示词片段."""
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return ""


def assemble_system_prompt(
    base: str = "base.md",
    persona: str = "assistant.md",
    tools: str = "tools.md",
    safety: str = "safety.md",
) -> str:
    """组装多片段系统提示词.

    默认加载 4 个片段: base (基础) + persona (人格) + tools (工具说明) + safety (安全规则)
    缺少任何文件时静默跳过.
    """
    parts = []
    for name in [base, persona, tools, safety]:
        text = load_prompt_file(name)
        if text:
            parts.append(text)

    if not parts:
        # 兜底
        return "You are a helpful AI assistant. Use tools when needed. Reply concisely."

    return "\n\n---\n\n".join(parts)
