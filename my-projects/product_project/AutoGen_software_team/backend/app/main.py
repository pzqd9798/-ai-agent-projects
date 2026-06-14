"""FastAPI 入口 — 组装所有路由 + 生命周期管理."""

import sys
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import config
from app.database import init_db
from app.services.observability import get_observability

# ---------------------------------------------------------------------------
# 路由导入
# ---------------------------------------------------------------------------

from app.api.auth import router as auth_router
from app.api.projects import router as projects_router
from app.api.phases import router as phases_router
from app.api.versions import router as versions_router
from app.api.ws import router as ws_router

# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动/关闭时的初始化与清理."""
    obs = get_observability()
    obs.info("app_starting", version=config.app.version)

    # 初始化数据库
    await init_db()
    obs.info("database_initialized")

    yield

    obs.info("app_stopping")
    # 清理资源
    from app.engine.agent_runner import AgentRunner
    # 无需显式清理, 进程退出即可
    obs.info("app_stopped")

# ---------------------------------------------------------------------------
# 应用实例
# ---------------------------------------------------------------------------

app = FastAPI(
    title=config.app.title,
    version=config.app.version,
    description="""AutoGen 多 Agent 软件研发团队 — 生产级升级版.

## 核心能力
- **三阶段流程**: 需求分析 → 代码生成 → 质量审查
- **多 Agent 协作**: ProductManager + Engineer + CodeReviewer + UserProxy
- **Agent 模板市场**: 全栈 Web / CLI 工具 / API 服务
- **版本历史**: Git 风格的文件追溯与回退
- **代码沙箱**: Docker 容器隔离执行
- **流式输出**: WebSocket / SSE 实时推送

## 快速开始
1. 注册账号: `POST /api/auth/register`
2. 创建项目: `POST /api/projects`
3. 执行阶段: `POST /api/projects/{id}/phases/plan`
4. 查看产物: `GET /api/projects/{id}/artifacts`
""",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# 中间件
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 路由注册
# ---------------------------------------------------------------------------

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(phases_router)
app.include_router(versions_router)
app.include_router(ws_router)


# ---------------------------------------------------------------------------
# 根路由 + 健康检查
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    """产品首页."""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Coding Agent</title>
<style>
  body {{ background:#0f172a; color:#e2e8f0; font-family:system-ui; display:flex;
         justify-content:center; align-items:center; min-height:100vh; margin:0; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:16px;
          padding:48px; max-width:600px; text-align:center; }}
  h1 {{ font-size:32px; color:#38bdf8; margin-bottom:8px; }}
  p {{ color:#94a3b8; line-height:1.8; }}
  .btn {{ display:inline-block; margin:12px 8px; padding:12px 24px; border-radius:8px;
          text-decoration:none; font-weight:600; }}
  .btn-docs {{ background:#38bdf8; color:#0f172a; }}
  .btn-health {{ background:#334155; color:#e2e8f0; }}
  .version {{ color:#64748b; font-size:14px; margin-top:24px; }}
</style>
</head>
<body>
<div class="card">
  <h1>🤖 Coding Agent</h1>
  <p>
    基于 AutoGen 多 Agent 协作的生产级软件研发平台<br>
    ProductManager → Engineer → CodeReviewer → UserProxy
  </p>
  <p>
    三阶段流程 · 模板市场 · 版本历史 · 代码沙箱 · 流式输出
  </p>
  <a class="btn btn-docs" href="/docs">📖 API 文档</a>
  <a class="btn btn-health" href="/health">💚 健康检查</a>
  <p class="version">v{config.app.version} · AutoGen</p>
</div>
</body>
</html>"""


@app.get("/health")
async def health():
    """健康检查端点."""
    obs = get_observability()
    metrics = obs.get_metrics_summary()
    return {
        "status": "healthy",
        "version": config.app.version,
        "total_phases": metrics["total_phase_executions"],
        "total_tokens": metrics["counters"].get("total_tokens", 0),
    }
