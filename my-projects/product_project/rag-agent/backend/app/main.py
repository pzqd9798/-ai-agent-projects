"""FastAPI 入口 — RAG Agent Pro.

生产级 RAG 知识助手平台:
    - 多租户认证 (JWT + API Key)
    - 知识库管理 (CRUD + 标签)
    - 文档摄取 (PDF/MD/TXT, 分块/嵌入/索引)
    - RAG 问答 (混合检索 + LLM 增强生成)
    - SSE 流式输出
    - 会话管理 + 长期记忆
    - SQLite 持久化 + Redis 异步任务
"""

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.config import config, llm
from app.database import init_db
from app.services.observability import get_logger, get_metrics
from app.engine.embedder import get_embedder, EMBEDDER_BACKEND

# ---------------------------------------------------------------------------
# 路由导入
# ---------------------------------------------------------------------------

from app.api.auth import router as auth_router
from app.api.knowledge import router as knowledge_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.ws import router as ws_router

# ---------------------------------------------------------------------------
# 生命周期
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    obs = get_logger()
    obs.info("app_starting", version=config.version)

    # 初始化数据库
    await init_db()
    obs.info("database_initialized")

    # 预热嵌入器
    try:
        emb = get_embedder()
        obs.info("embedder_ready", backend=EMBEDDER_BACKEND)
    except Exception as exc:
        obs.warning("embedder_init_failed", error=str(exc))

    start_time = time.time()
    yield

    uptime = time.time() - start_time
    obs.info("app_stopping", uptime_seconds=round(uptime, 1))
    obs.info("app_stopped")


# ---------------------------------------------------------------------------
# 应用实例
# ---------------------------------------------------------------------------

app = FastAPI(
    title=config.title,
    version=config.version,
    description="""企业级 RAG (检索增强生成) 知识助手平台.

## 核心能力
- **多格式文档摄取**: PDF, Markdown, TXT → 自动分块索引
- **混合检索**: BM25 关键词 + 向量语义 + 重排序
- **增强生成**: 检索 → 上下文组装 → LLM 流式生成
- **知识库管理**: 多知识库隔离、标签分类、全生命周期
- **双记忆系统**: 短期对话流 + 长期用户偏好
- **多租户认证**: JWT + API Key 双认证
- **SSE 流式输出**: 实时推送生成 token

## 快速开始
1. 注册: `POST /api/auth/register`
2. 创建知识库: `POST /api/knowledge`
3. 上传文档: `POST /api/documents/upload`
4. RAG 问答: `POST /api/chat`
5. 流式问答: `GET /ws/chat/stream`
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
app.include_router(knowledge_router)
app.include_router(chat_router)
app.include_router(documents_router)
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
<title>RAG Agent Pro</title>
<style>
  body {{ background:#0f172a; color:#e2e8f0; font-family:system-ui; display:flex;
         justify-content:center; align-items:center; min-height:100vh; margin:0; }}
  .card {{ background:#1e293b; border:1px solid #334155; border-radius:16px;
          padding:48px; max-width:640px; text-align:center; }}
  h1 {{ font-size:32px; color:#a78bfa; margin-bottom:8px; }}
  p {{ color:#94a3b8; line-height:1.8; }}
  .badge {{ display:inline-block; padding:4px 12px; margin:4px; border-radius:12px;
           background:#1e293b; border:1px solid #475569; font-size:13px; color:#cbd5e1; }}
  .btn {{ display:inline-block; margin:16px 8px; padding:12px 24px; border-radius:8px;
          text-decoration:none; font-weight:600; }}
  .btn-docs {{ background:#a78bfa; color:#0f172a; }}
  .btn-health {{ background:#334155; color:#e2e8f0; }}
  .version {{ color:#64748b; font-size:14px; margin-top:24px; }}
</style>
</head>
<body>
<div class="card">
  <h1>📚 RAG Agent Pro</h1>
  <p>
    企业级检索增强生成 (RAG) 知识助手平台<br>
    文档摄取 → 向量索引 → 混合检索 → 增强生成
  </p>
  <p>
    <span class="badge">BM25 + 向量</span>
    <span class="badge">SSE 流式</span>
    <span class="badge">多知识库</span>
    <span class="badge">双记忆</span>
    <span class="badge">PDF/MD/TXT</span>
  </p>
  <a class="btn btn-docs" href="/docs">📖 API 文档</a>
  <a class="btn btn-health" href="/health">💚 健康检查</a>
  <p class="version">v{config.version} · Embedder: {EMBEDDER_BACKEND}</p>
</div>
</body>
</html>"""


@app.get("/health")
async def health():
    """健康检查."""
    m = get_metrics()
    return {
        "status": "healthy",
        "version": config.version,
        "embedder": EMBEDDER_BACKEND,
        "model": llm.model_id,
        "metrics": m.get_summary(),
    }
