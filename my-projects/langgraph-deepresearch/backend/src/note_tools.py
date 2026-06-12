"""File-based note operations (replaces hello-agents NoteTool).

Provides create / read / update note actions backed by markdown files.
Compatible with the [TOOL_CALL:note:{...}] text-based calling convention.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


class NoteTool:
    """Simple file-based note tool with the same interface as hello-agents NoteTool.

    Notes are stored as ``{note_id}.md`` files under *workspace*.
    """

    def __init__(self, workspace: str = "./notes") -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public entry-point (mirrors hello-agents NoteTool.run)
    # ------------------------------------------------------------------

    def run(self, params: dict[str, Any]) -> str:
        action = str(params.get("action", "")).strip().lower()
        if action == "create":
            return self._create(params)
        if action == "read":
            return self._read(params)
        if action == "update":
            return self._update(params)
        return f"❌ 未知操作: {action}，支持 create / read / update"

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _create(self, params: dict[str, Any]) -> str:
        note_id = str(params.get("note_id") or uuid.uuid4().hex[:8])
        title = str(params.get("title") or "Untitled")
        content = str(params.get("content") or "")
        note_type = str(params.get("note_type") or "general")
        tags = params.get("tags") or []

        tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)

        body = f"# {title}\n\n"
        body += f"**ID**: {note_id}\n"
        body += f"**Type**: {note_type}\n"
        if tags_str:
            body += f"**Tags**: {tags_str}\n"
        body += f"\n{content}\n"

        file_path = self.workspace / f"{note_id}.md"
        file_path.write_text(body, encoding="utf-8")

        return f"✅ 笔记已创建\nID: {note_id}\n文件: {file_path}"

    def _read(self, params: dict[str, Any]) -> str:
        note_id = str(params.get("note_id") or "")
        if not note_id:
            return "❌ 缺少 note_id 参数"

        file_path = self.workspace / f"{note_id}.md"
        if not file_path.exists():
            return f"❌ 笔记不存在: {note_id}"

        content = file_path.read_text(encoding="utf-8")
        return f"📄 笔记内容 (ID: {note_id}):\n{content}"

    def _update(self, params: dict[str, Any]) -> str:
        note_id = str(params.get("note_id") or "")
        if not note_id:
            return "❌ 缺少 note_id 参数"

        file_path = self.workspace / f"{note_id}.md"
        if not file_path.exists():
            return f"❌ 笔记不存在: {note_id}，请先创建"

        existing = file_path.read_text(encoding="utf-8")
        new_content = str(params.get("content") or "")
        title = str(params.get("title") or "")

        # Replace title if provided and different
        if title:
            lines = existing.split("\n")
            if lines and lines[0].startswith("# "):
                lines[0] = f"# {title}"
            existing = "\n".join(lines)

        if new_content:
            existing += f"\n\n---\n{new_content}\n"

        file_path.write_text(existing, encoding="utf-8")

        return f"✅ 笔记已更新\nID: {note_id}\n文件: {file_path}"
