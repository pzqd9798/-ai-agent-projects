"""FastAPI 主入口 — Agent API 服务化.

启动方式:
    python -m uvicorn app.main:app --reload
    # 或
    python app/main.py
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import asyncio
import json

from app.config import config
from app.engine.agent_loop import Agent
from app.security.guard import scan_input, sanitize_output, check_tool_permission
from app.intelligence.soul import assemble_system_prompt



app = FastAPI(
    title="Agent Platform",
    description="生产级 AI Agent 平台 — 多通道接入、工具调度、记忆系统、安全防护",
    version="0.1.0",
)

# 全局 Agent 实例
_agent: Agent | None = None


def get_agent(session_id: str | None = None) -> Agent:
    global _agent
    if _agent is None:
        system_prompt = assemble_system_prompt()
        _agent = Agent(system_prompt=system_prompt)
        _agent.load_or_create_session(session_id)
    return _agent


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class AgentRequest(BaseModel):
    message: str = Field(..., description="用户消息", examples=["搜索Python最新版本"])
    session_id: str | None = Field(None, description="会话ID，不传则自动创建或恢复")
    peer_id: str = Field("api-user", description="用户标识")

    model_config = {"extra": "allow"}


class AgentResponse(BaseModel):
    reply: str = Field(..., description="Agent 回复")
    session_id: str = Field(..., description="当前会话ID")
    context_usage_pct: float = Field(0.0, description="上下文使用百分比")
    safety: dict = Field(default_factory=dict, description="安全检查结果")


class HealthResponse(BaseModel):
    status: str = "ok"
    model: str = ""
    tools: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    from app.engine.tool_registry import TOOL_HANDLERS
    return HealthResponse(
        status="ok",
        model=config.llm.model_id,
        tools=list(TOOL_HANDLERS.keys()),
    )


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(req: AgentRequest):
    """同步 Agent 调用 — 发送消息并获取完整回复."""
    # 安全检查: 输入
    scan_result = scan_input(req.message)
    if not scan_result["safe"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "输入安全检查未通过", "reasons": scan_result["reasons"]},
        )

    try:
        agent = get_agent(req.session_id)
        reply = agent.run_turn(req.message)

        # 安全检查: 输出脱敏
        reply, replaced = sanitize_output(reply)

        _, _, pct = agent.get_context_usage()

        return AgentResponse(
            reply=reply,
            session_id=agent.session_store.current_session_id or "",
            context_usage_pct=round(pct, 1),
            safety={"input_safe": True, "output_sanitized": replaced},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/agent/stream")
async def agent_stream(req: AgentRequest):
    """流式 Agent 调用 — SSE (Server-Sent Events)."""
    scan_result = scan_input(req.message)
    if not scan_result["safe"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "输入安全检查未通过", "reasons": scan_result["reasons"]},
        )

    async def generate():
        try:
            # 在线程池中运行同步 Agent 以免阻塞事件循环
            loop = asyncio.get_event_loop()
            agent = get_agent(req.session_id)
            reply = await loop.run_in_executor(None, agent.run_turn, req.message)
            reply, _ = sanitize_output(reply)

            # 模拟流式输出 (逐段发送)
            chunk_size = 10
            for i in range(0, len(reply), chunk_size):
                chunk = reply[i:i + chunk_size]
                yield f"data: {json.dumps({'token': chunk})}\n\n"
                await asyncio.sleep(0.02)

            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/agent/compact")
async def compact(req: AgentRequest):
    """手动压缩会话历史."""
    agent = get_agent(req.session_id)
    reduced = agent.compact_now()
    _, _, pct = agent.get_context_usage()
    return {"reduced_by": reduced, "context_usage_pct": round(pct, 1)}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    import uvicorn
    server = config.server
    # 预加载内置工具
    import app.tools.builtin  # noqa: F401
    print(f"Agent Platform 启动: http://{server.host}:{server.port}")
    print(f"API 文档: http://{server.host}:{server.port}/docs")
    uvicorn.run("app.main:app", host=server.host, port=server.port, reload=True)


if __name__ == "__main__":
    main()
