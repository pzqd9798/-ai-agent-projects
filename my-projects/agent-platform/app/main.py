"""ClawBot — 企业级 AI Agent 服务平台.

启动方式:
    python -m uvicorn app.main:app --reload
    python app/main.py

核心端点:
    GET  /           产品首页
    GET  /admin      管理后台
    GET  /health     健康检查
    POST /agent      Agent 调用
    POST /agent/stream  SSE 流式调用
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
import asyncio
import json

from app.config import config
from app.engine.agent_loop import Agent
from app.security.guard import scan_input, sanitize_output
from app.intelligence.soul import assemble_system_prompt
from app.models.database import init_db

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ClawBot",
    description="企业级 AI Agent 服务平台 — 一键部署、多场景模板、多通道接入",
    version="0.2.0",
)

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

init_db()

from app.admin.api import router as admin_api_router
from app.admin.dashboard import router as admin_dash_router

app.include_router(admin_api_router)
app.include_router(admin_dash_router)

# Agent 池: agent_id -> Agent 实例
_agent_pool: dict[str, Agent] = {}


def get_or_create_agent(agent_id: str = "default") -> Agent:
    if agent_id not in _agent_pool:
        system_prompt = assemble_system_prompt()
        agent = Agent(system_prompt=system_prompt, agent_id=agent_id)
        agent.load_or_create_session()
        _agent_pool[agent_id] = agent
    return _agent_pool[agent_id]


# ---------------------------------------------------------------------------
# 产品首页
# ---------------------------------------------------------------------------

LANDING_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>ClawBot — 企业级 AI Agent 服务平台</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--accent:#38bdf8;--dim:#94a3b8;--green:#4ade80}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif}
.container{max-width:1100px;margin:0 auto;padding:0 24px}
.hero{padding:80px 0 60px;text-align:center}
.hero h1{font-size:48px;margin-bottom:16px;background:linear-gradient(135deg,var(--accent),#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero p{font-size:18px;color:var(--dim);max-width:600px;margin:0 auto 32px}
.btn{padding:12px 28px;border-radius:8px;border:none;cursor:pointer;font-size:15px;font-weight:600;text-decoration:none;display:inline-block}
.btn-primary{background:var(--accent);color:#0f172a}
.btn-outline{border:1px solid var(--accent);color:var(--accent);margin-left:12px}
.features{padding:60px 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}
.feature{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:28px}
.feature h3{font-size:18px;margin:12px 0 8px}
.feature p{color:var(--dim);font-size:14px;line-height:1.7}
.feature .icon{font-size:32px}
.quickstart{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:40px;margin:40px 0}
.quickstart h2{margin-bottom:20px}
.quickstart pre{background:#0f172a;padding:20px;border-radius:8px;overflow-x:auto;font-size:13px;line-height:1.8}
.footer{text-align:center;padding:40px 0;color:var(--dim);font-size:13px;border-top:1px solid var(--border);margin-top:60px}
</style>
</head>
<body>
<div class="container">
  <div class="hero">
    <h1>🤖 ClawBot</h1>
    <p>一键部署的企业级 AI Agent 服务平台。从代码助手到智能客服，30 秒启动，开箱即用。</p>
    <a href="/admin" class="btn btn-primary">进入管理后台</a>
    <a href="/docs" class="btn btn-outline">API 文档</a>
  </div>

  <div class="features">
    <div class="feature">
      <div class="icon">📦</div>
      <h3>场景模板</h3>
      <p>预置代码助手、智能客服、文档问答等场景模板。选择模板，配置工具，一键创建专属 Agent。</p>
    </div>
    <div class="feature">
      <div class="icon">🔗</div>
      <h3>多通道接入</h3>
      <p>REST API、SSE 流式、Telegram Bot、Web UI — 一套后端服务所有通道，统一的 InboundMessage 抽象。</p>
    </div>
    <div class="feature">
      <div class="icon">🛡️</div>
      <h3>三层安全</h3>
      <p>输入注入检测、输出敏感信息脱敏、工具权限控制。企业级安全护栏，Prompt 注入防御。</p>
    </div>
    <div class="feature">
      <div class="icon">🧠</div>
      <h3>长期记忆</h3>
      <p>短期对话上下文 + 长期用户偏好记忆。Redis 双记忆架构，跨会话保持用户信息。</p>
    </div>
    <div class="feature">
      <div class="icon">🔧</div>
      <h3>工具生态</h3>
      <p>Shell 命令、文件读写、网页搜索、浏览器自动化 — 工具注册表热插拔，加工具不改核心循环。</p>
    </div>
    <div class="feature">
      <div class="icon">🐳</div>
      <h3>一键部署</h3>
      <p><code>docker-compose up -d</code>，30 秒启动完整服务（Agent + Redis + 管理后台）。</p>
    </div>
  </div>

  <div class="quickstart">
    <h2>🚀 30 秒启动</h2>
    <pre>git clone https://github.com/pzqd9798/-ai-agent-projects.git
cd -ai-agent-projects/my-projects/agent-platform
cp .env.example .env
<span style="color:var(--dim)"># 编辑 .env 填入 ANTHROPIC_API_KEY</span>
docker-compose up -d
<span style="color:var(--dim)"># 打开 http://localhost:8000</span></pre>
  </div>

  <div class="footer">
    ClawBot v0.2.0 · MIT License · <a href="https://github.com/pzqd9798/-ai-agent-projects" style="color:var(--accent)">GitHub</a>
  </div>
</div>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def landing():
    return LANDING_HTML


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class AgentRequest(BaseModel):
    message: str = Field(..., description="用户消息", examples=["搜索Python最新版本"])
    session_id: str | None = Field(None, description="会话ID，不传则自动创建或恢复")
    agent_id: str = Field("default", description="Agent ID")
    peer_id: str = Field("api-user", description="用户标识")
    model_config = {"extra": "allow"}


class AgentResponse(BaseModel):
    reply: str = Field(..., description="Agent 回复")
    session_id: str = Field(..., description="当前会话ID")
    context_usage_pct: float = Field(0.0, description="上下文使用百分比")
    safety: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.2.0"
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
        version="0.2.0",
        model=config.llm.model_id,
        tools=list(TOOL_HANDLERS.keys()),
    )


@app.post("/agent", response_model=AgentResponse)
async def agent_endpoint(req: AgentRequest):
    scan_result = scan_input(req.message)
    if not scan_result["safe"]:
        raise HTTPException(
            status_code=400,
            detail={"error": "输入安全检查未通过", "reasons": scan_result["reasons"]},
        )
    try:
        agent = get_or_create_agent(req.agent_id)
        reply = agent.run_turn(req.message)
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
    scan_result = scan_input(req.message)
    if not scan_result["safe"]:
        raise HTTPException(status_code=400, detail={"error": "输入安全检查未通过", "reasons": scan_result["reasons"]})

    async def generate():
        try:
            loop = asyncio.get_event_loop()
            agent = get_or_create_agent(req.agent_id)
            reply = await loop.run_in_executor(None, agent.run_turn, req.message)
            reply, _ = sanitize_output(reply)
            chunk_size = 10
            for i in range(0, len(reply), chunk_size):
                yield f"data: {json.dumps({'token': reply[i:i+chunk_size]})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/agent/compact")
async def compact(req: AgentRequest):
    agent = get_or_create_agent(req.agent_id)
    reduced = agent.compact_now()
    _, _, pct = agent.get_context_usage()
    return {"reduced_by": reduced, "context_usage_pct": round(pct, 1)}


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    import uvicorn
    import app.tools.builtin  # noqa: F401
    server = config.server
    print(f"🤖 ClawBot v0.2.0")
    print(f"   首页:     http://{server.host}:{server.port}")
    print(f"   管理后台: http://{server.host}:{server.port}/admin")
    print(f"   API文档:  http://{server.host}:{server.port}/docs")
    print(f"   默认密码: admin / admin123")
    uvicorn.run("app.main:app", host=server.host, port=server.port, reload=True)


if __name__ == "__main__":
    main()
