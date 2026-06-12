"""会话持久化 — JSONL 追加写 + 重建 API 格式.

基于 claw0 s03 SessionStore:
    写入时追加 (原子操作)
    读取时重放 (_rebuild_history 将扁平 JSONL 转回 API 格式)
    四种记录类型: user, assistant, tool_use, tool_result
"""

import json
import uuid
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


class SessionStore:
    """管理 Agent 会话的 JSONL 持久化存储."""

    def __init__(self, agent_id: str = "default", base_dir: Path | None = None):
        from app.config import config
        self.agent_id = agent_id
        self.base_dir = base_dir or config.session.session_dir
        self.sessions_dir = self.base_dir / "agents" / agent_id / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.index_path = self.sessions_dir.parent / "sessions.json"
        self._index: dict[str, dict] = self._load_index()
        self.current_session_id: str | None = None

    # ------------------------------------------------------------------
    # 索引管理
    # ------------------------------------------------------------------

    def _load_index(self) -> dict[str, dict]:
        if self.index_path.exists():
            try:
                return json.loads(self.index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_index(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(self._index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _session_path(self, session_id: str) -> Path:
        return self.sessions_dir / f"{session_id}.jsonl"

    # ------------------------------------------------------------------
    # 会话 CRUD
    # ------------------------------------------------------------------

    def create_session(self, label: str = "") -> str:
        sid = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._index[sid] = {
            "label": label, "created_at": now,
            "last_active": now, "message_count": 0,
        }
        self._save_index()
        self._session_path(sid).touch()
        self.current_session_id = sid
        return sid

    def load_session(self, session_id: str) -> list[dict]:
        path = self._session_path(session_id)
        if not path.exists():
            return []
        self.current_session_id = session_id
        return self._rebuild_history(path)

    def delete_session(self, session_id: str) -> None:
        path = self._session_path(session_id)
        if path.exists():
            path.unlink()
        self._index.pop(session_id, None)
        self._save_index()

    def list_sessions(self) -> list[tuple[str, dict]]:
        items = list(self._index.items())
        items.sort(key=lambda x: x[1].get("last_active", ""), reverse=True)
        return items

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def save_turn(self, role: str, content: Any) -> None:
        if not self.current_session_id:
            return
        self._append_record(self.current_session_id, {
            "type": role, "content": content, "ts": time.time(),
        })

    def save_tool_result(self, tool_use_id: str, name: str,
                         tool_input: dict, result: str) -> None:
        if not self.current_session_id:
            return
        ts = time.time()
        self._append_record(self.current_session_id, {
            "type": "tool_use", "tool_use_id": tool_use_id,
            "name": name, "input": tool_input, "ts": ts,
        })
        self._append_record(self.current_session_id, {
            "type": "tool_result", "tool_use_id": tool_use_id,
            "content": result, "ts": ts,
        })

    def _append_record(self, session_id: str, record: dict) -> None:
        path = self._session_path(session_id)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if session_id in self._index:
            self._index[session_id]["last_active"] = datetime.now(timezone.utc).isoformat()
            self._index[session_id]["message_count"] += 1
            self._save_index()

    # ------------------------------------------------------------------
    # 核心: 从 JSONL 重建 API 格式的 messages[]
    # ------------------------------------------------------------------
    # Anthropic API 要求:
    #   - 消息必须 user/assistant 严格交替
    #   - tool_use 块属于 assistant 消息
    #   - tool_result 块属于 user 消息
    #   - 连续的 tool_result 合并到同一条 user 消息
    # ------------------------------------------------------------------

    def _rebuild_history(self, path: Path) -> list[dict]:
        messages: list[dict] = []
        lines = path.read_text(encoding="utf-8").strip().split("\n")

        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = record.get("type")

            if rtype == "user":
                messages.append({"role": "user", "content": record["content"]})

            elif rtype == "assistant":
                content = record["content"]
                if isinstance(content, str):
                    content = [{"type": "text", "text": content}]
                messages.append({"role": "assistant", "content": content})

            elif rtype == "tool_use":
                block = {
                    "type": "tool_use", "id": record["tool_use_id"],
                    "name": record["name"], "input": record["input"],
                }
                if messages and messages[-1]["role"] == "assistant":
                    content = messages[-1]["content"]
                    if isinstance(content, list):
                        content.append(block)
                else:
                    messages.append({"role": "assistant", "content": [block]})

            elif rtype == "tool_result":
                block = {
                    "type": "tool_result",
                    "tool_use_id": record["tool_use_id"],
                    "content": record["content"],
                }
                # 合并连续的 tool_result
                if (messages and messages[-1]["role"] == "user"
                        and isinstance(messages[-1]["content"], list)
                        and messages[-1]["content"]
                        and isinstance(messages[-1]["content"][0], dict)
                        and messages[-1]["content"][0].get("type") == "tool_result"):
                    messages[-1]["content"].append(block)
                else:
                    messages.append({"role": "user", "content": [block]})

        return messages
