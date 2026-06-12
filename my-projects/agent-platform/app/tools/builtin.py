#!/usr/bin/env python3
"""内置工具集 — 注册到 tool_registry 供 Agent 调用."""

import os
import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone

from app.engine.tool_registry import register_tool, TOOLS, TOOL_HANDLERS
from app.config import config

WORKDIR = Path.cwd()
MAX_OUTPUT = config.session.max_tool_output


# ---------------------------------------------------------------------------
# 安全辅助
# ---------------------------------------------------------------------------

def _safe_path(raw: str, base: Path | None = None) -> Path:
    """防止路径穿越."""
    base = base or WORKDIR
    target = (base / raw).resolve()
    if not str(target).startswith(str(base.resolve())):
        raise ValueError(f"路径穿越被阻止: {raw}")
    return target


def _truncate(text: str, limit: int = MAX_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [截断, 共 {len(text)} 字符]"


# ---------------------------------------------------------------------------
# 1. bash — 执行 Shell 命令
# ---------------------------------------------------------------------------

def tool_bash(command: str, timeout: int = 30) -> str:
    dangerous = ["rm -rf /", "mkfs", "> /dev/sd", "dd if=", "format c:"]
    for pattern in dangerous:
        if pattern in command.lower():
            return f"错误: 拒绝执行危险命令 '{pattern}'"

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=str(WORKDIR),
        )
        output = result.stdout or ""
        if result.stderr:
            output += ("\n--- stderr ---\n" + result.stderr) if output else result.stderr
        if result.returncode != 0:
            output += f"\n[退出码: {result.returncode}]"
        return _truncate(output) if output else "[无输出]"
    except subprocess.TimeoutExpired:
        return f"错误: 命令超时 ({timeout}s)"
    except Exception as exc:
        return f"错误: {exc}"


register_tool("bash", "执行 Shell 命令并返回输出。用于系统命令、git、包管理等。", {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "要执行的 Shell 命令。"},
        "timeout": {"type": "integer", "description": "超时秒数，默认 30。"},
    },
    "required": ["command"],
}, tool_bash)


# ---------------------------------------------------------------------------
# 2. read_file — 读取文件
# ---------------------------------------------------------------------------

def tool_read_file(file_path: str) -> str:
    try:
        target = _safe_path(file_path)
        if not target.exists():
            return f"错误: 文件不存在: {file_path}"
        if not target.is_file():
            return f"错误: 不是文件: {file_path}"
        return _truncate(target.read_text(encoding="utf-8"))
    except ValueError as exc:
        return str(exc)
    except Exception as exc:
        return f"错误: {exc}"


register_tool("read_file", "读取文件内容。", {
    "type": "object",
    "properties": {
        "file_path": {"type": "string", "description": "文件路径 (相对于工作目录)。"},
    },
    "required": ["file_path"],
}, tool_read_file)


# ---------------------------------------------------------------------------
# 3. write_file — 写入文件
# ---------------------------------------------------------------------------

def tool_write_file(file_path: str, content: str) -> str:
    try:
        target = _safe_path(file_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"成功写入 {len(content)} 字符到 {file_path}"
    except ValueError as exc:
        return str(exc)
    except Exception as exc:
        return f"错误: {exc}"


register_tool("write_file", "写入内容到文件。父目录自动创建。会覆盖已有内容。", {
    "type": "object",
    "properties": {
        "file_path": {"type": "string", "description": "文件路径。"},
        "content": {"type": "string", "description": "要写入的内容。"},
    },
    "required": ["file_path", "content"],
}, tool_write_file)


# ---------------------------------------------------------------------------
# 4. web_fetch — 获取网页内容
# ---------------------------------------------------------------------------

def tool_web_fetch(url: str) -> str:
    import httpx
    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True,
                         headers={"User-Agent": "AgentPlatform/1.0"})
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            text = resp.text[:MAX_OUTPUT]
            # 简易提取可见文本 (去掉 HTML 标签)
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return _truncate(text)
        return _truncate(resp.text)
    except Exception as exc:
        return f"错误: 获取 {url} 失败: {exc}"


register_tool("web_fetch", "获取公开网页的文本内容。用于提取文章、文档等信息。", {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "目标网页 URL。"},
    },
    "required": ["url"],
}, tool_web_fetch)


# ---------------------------------------------------------------------------
# 5. get_current_time — 获取当前时间
# ---------------------------------------------------------------------------

def tool_get_current_time() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC")


register_tool("get_current_time", "获取当前 UTC 日期和时间。", {
    "type": "object",
    "properties": {},
    "required": [],
}, tool_get_current_time)
