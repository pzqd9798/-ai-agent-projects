"""Agent 核心循环 — while True + stop_reason + 工具调度.

基于 claw0 s01-s03, 这是整个平台的心脏:
    User Input → messages[] → LLM API (tools=TOOLS) → stop_reason?
                                                        /          \
                                                  "end_turn"    "tool_use"
                                                      |              |
                                                   返回文本      执行工具→反馈→继续

所有上层功能 (通道、记忆、安全、UI) 都围绕这个循环叠加, 循环结构本身不变.
"""

from anthropic import Anthropic

from app.config import config
from app.engine.tool_registry import TOOLS, TOOL_HANDLERS, process_tool_call
from app.engine.context_guard import ContextGuard
from app.engine.session_store import SessionStore


class Agent:
    """生产级 Agent — 支持工具调用、会话持久化、上下文保护."""

    def __init__(
        self,
        system_prompt: str = "You are a helpful AI assistant. Use tools when needed. Be concise.",
        agent_id: str = "default",
    ):
        self.llm_config = config.llm
        self.client = Anthropic(
            api_key=self.llm_config.api_key,
            base_url=self.llm_config.base_url,
        )
        self.system_prompt = system_prompt
        self.session_store = SessionStore(agent_id=agent_id)
        self.context_guard = ContextGuard()
        self.messages: list[dict] = []
        self._on_tool_call: list[callable] = []

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def load_or_create_session(self, session_id: str | None = None) -> str:
        """加载已有会话或创建新会话."""
        if session_id:
            self.messages = self.session_store.load_session(session_id)
            return session_id

        sessions = self.session_store.list_sessions()
        if sessions:
            sid = sessions[0][0]
            self.messages = self.session_store.load_session(sid)
            print(f"[Agent] 恢复会话: {sid} ({len(self.messages)} 条消息)")
            return sid

        sid = self.session_store.create_session("default")
        self.messages = []
        print(f"[Agent] 创建新会话: {sid}")
        return sid

    # ------------------------------------------------------------------
    # 执行一轮 (处理一条用户消息, 可能触发多轮工具调用)
    # ------------------------------------------------------------------

    def run_turn(self, user_input: str) -> str:
        """执行一轮对话: 用户输入 → LLM → (可能工具调用 → LLM → ...) → 文本回复."""
        # 1. 追加用户消息
        self.messages.append({"role": "user", "content": user_input})
        self.session_store.save_turn("user", user_input)

        # 2. 内层循环: 处理工具调用链
        while True:
            response = self.context_guard.guard_api_call(
                api_client=self.client,
                model=self.llm_config.model_id,
                system=self.system_prompt,
                messages=self.messages,
                tools=TOOLS if TOOLS else None,
            )

            # 序列化 assistant 响应并持久化
            serialized = []
            for block in response.content:
                if hasattr(block, "text"):
                    serialized.append({"type": "text", "text": block.text})
                elif hasattr(block, "type") and block.type == "tool_use":
                    serialized.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    })

            self.messages.append({"role": "assistant", "content": response.content})
            self.session_store.save_turn("assistant", serialized)

            # 3. 根据 stop_reason 分支
            if response.stop_reason == "end_turn":
                return self._extract_text(response)

            elif response.stop_reason == "tool_use":
                tool_results = self._execute_tools(response)
                self.messages.append({"role": "user", "content": tool_results})
                # 继续内层循环
                continue

            else:
                text = self._extract_text(response)
                if text:
                    return text
                return f"[stop_reason={response.stop_reason}]"

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _execute_tools(self, response) -> list[dict]:
        """执行所有工具调用, 返回 tool_result 块列表."""
        results = []
        for block in response.content:
            if not hasattr(block, "type") or block.type != "tool_use":
                continue

            print(f"  [tool: {block.name}]")
            result = process_tool_call(block.name, block.input)

            # 持久化
            self.session_store.save_tool_result(
                block.id, block.name, block.input, result
            )

            # 触发回调
            for cb in self._on_tool_call:
                try:
                    cb(block.name, block.input, result)
                except Exception:
                    pass

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
        return results

    @staticmethod
    def _extract_text(response) -> str:
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts)

    # ------------------------------------------------------------------
    # 回调
    # ------------------------------------------------------------------

    def on_tool_call(self, callback: callable) -> None:
        """注册工具调用回调, 用于安全审计/追踪."""
        self._on_tool_call.append(callback)

    # ------------------------------------------------------------------
    # 上下文管理
    # ------------------------------------------------------------------

    def get_context_usage(self) -> tuple[int, int, float]:
        """返回 (estimated_tokens, max_tokens, percentage)."""
        estimated = self.context_guard.estimate_messages_tokens(self.messages)
        max_tokens = self.context_guard.max_tokens
        return estimated, max_tokens, (estimated / max_tokens) * 100

    def compact_now(self) -> int:
        """手动压缩历史, 返回压缩后的消息数."""
        old_len = len(self.messages)
        self.messages = self.context_guard.compact_history(
            self.messages, self.client, self.llm_config.model_id
        )
        return len(self.messages) - old_len
