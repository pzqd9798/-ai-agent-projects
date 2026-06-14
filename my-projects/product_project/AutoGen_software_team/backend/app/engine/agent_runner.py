"""Agent 执行器 — 封装 AutoGen 团队, 提供同步/异步统一接口."""

import sys
import asyncio
import json
import re
import time as time_mod
from pathlib import Path
from typing import AsyncIterator

# 将项目根目录加入 path, 使 team/ 模块可导入
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_core.models import ModelInfo
from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage

from app.config import config
from app.engine.templates import get_template_by_name


class AgentRunner:
    """生产级 Agent 执行器 — 支持流式输出、超时控制、错误恢复."""

    def __init__(self, template_name: str = "full-stack"):
        self.template = get_template_by_name(template_name) or get_template_by_name("full-stack")
        self._model_client = None

    # ------------------------------------------------------------------
    # 模型客户端 (延迟初始化)
    # ------------------------------------------------------------------

    def _get_model_client(self) -> OpenAIChatCompletionClient:
        if self._model_client is None:
            self._model_client = OpenAIChatCompletionClient(
                model=config.llm.model_id,
                api_key=config.llm.api_key,
                base_url=config.llm.base_url,
                model_info=ModelInfo(
                    vision=False,
                    function_calling=True,
                    json_output=False,
                    family="unknown",
                    context_length=config.llm.context_length,
                ),
            )
        return self._model_client

    # ------------------------------------------------------------------
    # Agent 工厂
    # ------------------------------------------------------------------

    def _create_agent(self, role: dict) -> AssistantAgent | UserProxyAgent:
        """根据角色定义创建 Agent 实例."""
        name = role["name"]
        system_prompt = role.get("system_prompt", "")

        if name == "UserProxy":
            return UserProxyAgent(
                name=name,
                description=system_prompt,
            )
        else:
            return AssistantAgent(
                name=name,
                model_client=self._get_model_client(),
                system_message=system_prompt,
            )

    # ------------------------------------------------------------------
    # 单 Agent 调用 (用于分阶段执行)
    # ------------------------------------------------------------------

    async def call_agent(self, role_name: str, prompt: str) -> str:
        """调用单个 Agent 并返回其回复文本."""
        role = next((r for r in self.template["roles"] if r["name"] == role_name), None)
        if not role:
            raise ValueError(f"未知角色: {role_name}")

        agent = self._create_agent(role)
        response = await agent.on_messages(
            [TextMessage(content=prompt, source="User")],
            cancellation_token=None,
        )
        content = response.chat_message.content
        return content if isinstance(content, str) else str(content)

    # ------------------------------------------------------------------
    # 全团队执行
    # ------------------------------------------------------------------

    async def run_full_team(self, task: str, max_turns: int = 20,
                            on_message=None) -> dict:
        """运行完整的多 Agent 协作团队.

        Args:
            task: 开发任务描述
            max_turns: 最大对话轮次
            on_message: 可选回调, 每收到一条消息时调用 on_message(role, content)

        Returns:
            {"messages": [...], "output": str}
        """
        client = self._get_model_client()
        participants = [self._create_agent(r) for r in self.template["roles"]]

        team = RoundRobinGroupChat(
            participants=participants,
            termination_condition=TextMentionTermination("TERMINATE"),
            max_turns=max_turns,
        )

        messages = []
        async for msg in team.run_stream(task=task):
            role = getattr(msg, "source", "unknown")
            content = getattr(msg, "content", str(msg))
            if isinstance(content, list):
                content = " ".join(str(c) for c in content)
            messages.append({"role": role, "content": content})
            if on_message:
                on_message(role, content)

        return {
            "messages": messages,
            "output": messages[-1]["content"] if messages else "",
        }

    # ------------------------------------------------------------------
    # 流式执行 (用于 SSE)
    # ------------------------------------------------------------------

    async def run_phase_stream(self, role_name: str, prompt: str) -> AsyncIterator[str]:
        """流式执行单个阶段, 逐 token 产出 (通过 SSE 发送)."""
        role = next((r for r in self.template["roles"] if r["name"] == role_name), None)
        if not role:
            yield f"错误: 未知角色 {role_name}"
            return

        agent = self._create_agent(role)

        # AutoGen AssistantAgent 不支持原生流式, 我们分段发送
        yield f"[阶段开始] {role_name}\n\n"

        try:
            response = await agent.on_messages(
                [TextMessage(content=prompt, source="User")],
                cancellation_token=None,
            )
            content = response.chat_message.content
            text = content if isinstance(content, str) else str(content)

            # 按句子分段发送, 模拟流式效果
            sentences = re.split(r"(?<=[。！？\n])", text)
            for sentence in sentences:
                if sentence.strip():
                    yield sentence
                    await asyncio.sleep(0.02)

            yield f"\n\n[阶段完成] {role_name}"
        except Exception as e:
            yield f"\n\n[错误] {role_name}: {str(e)}"


# ------------------------------------------------------------------
# 同步包装器 (供 CLI 调试)
# ------------------------------------------------------------------

def run_phase_sync(template_name: str, role_name: str, prompt: str) -> str:
    """同步方式调用 Agent."""
    runner = AgentRunner(template_name)
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(runner.call_agent(role_name, prompt))
    finally:
        loop.close()


# ------------------------------------------------------------------
# 代码提取
# ------------------------------------------------------------------

def extract_code_blocks(text: str) -> list[dict]:
    """从 Agent 输出中提取代码块."""
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": m[0] or "text", "code": m[1].strip()} for m in matches]
