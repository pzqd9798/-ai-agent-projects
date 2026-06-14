# Deep Research Platform

生产级多 Agent 深度研究平台。LangGraph 编排 × 6 搜索引擎 × 原生 Function Calling × JWT 多租户 × SSE 流式 × Docker 部署。

## 架构

```
用户输入研究主题
    │
    ▼
┌─────────────────────────────────────────────────┐
│  FastAPI Gateway (JWT + API Key + Rate Limit)   │
├─────────────────────────────────────────────────┤
│  LangGraph StateGraph Orchestrator              │
│                                                  │
│   plan ──→ search ──→ summarize ──→ report      │
│             ↑                    │               │
│             └──── continue? ─────┘               │
├─────────────────────────────────────────────────┤
│  Services: Planner · Searcher · Summarizer      │
│            Reporter · Session · Memory           │
├─────────────────────────────────────────────────┤
│  Search: Tavily · DuckDuckGo · SearXNG           │
│          Perplexity · Advanced (multi-fusion)    │
├─────────────────────────────────────────────────┤
│  SQLite (7 tables): Users · Sessions · Notes     │
│  SearchResults · SourceCache · UsageLogs         │
└─────────────────────────────────────────────────┘
    │
    ▼
Vue 3 Frontend (SSE streaming · Router · Pinia)
```

## 10 层生产级升级

| # | 层级 | 说明 |
|:--:|------|------|
| 1 | **认证安全** | JWT + API Key 双认证、速率限制、Prompt 注入检测 |
| 2 | **数据持久化** | SQLAlchemy async ORM、7 张表、Alembic 迁移 |
| 3 | **测试体系** | pytest-asyncio、temp database 隔离、12+ 集成测试 |
| 4 | **LangGraph 编排** | StateGraph 替代手动循环、checkpoint、条件路由 |
| 5 | **原生工具调用** | OpenAI/Anthropic tool_use 替代 `[TOOL_CALL]` 文本解析 |
| 6 | **搜索增强** | 6 后端 + Perplexity 实现 + 多源融合 + TTL 缓存 |
| 7 | **流式可观测** | SSE token-level 推送、JSON 结构化日志、Prometheus 指标 |
| 8 | **记忆系统** | 短期滑动窗口 + 长期跨会话 SQLite 持久化 |
| 9 | **前端重构** | Vue Router + Pinia + 组件拆分 (15+) |
| 10 | **DevOps** | Docker 多阶段构建、Compose 4 服务、GitHub Actions CI |

## 快速开始

```bash
# 1. 配置环境
cd backend
cp .env.example .env
# 编辑 .env — 填入 LLM_API_KEY 等

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动 API
python src/main.py          # http://localhost:8000/docs

# 4. 启动前端 (另一个终端)
cd frontend
npm install
npm run dev                 # http://localhost:5173
```

## Docker 部署

```bash
# 仅 API
docker-compose up api

# 全栈 (API + SearXNG + Frontend)
docker-compose --profile full up

# 开发模式
docker-compose --profile dev up
```

## API 概览

| 方法 | 端点 | 说明 | 认证 |
|------|------|------|:--:|
| `POST` | `/api/auth/register` | 注册用户 | - |
| `POST` | `/api/auth/login` | 登录获取 JWT | - |
| `GET` | `/api/auth/me` | 用户信息+统计 | JWT/Key |
| `POST` | `/api/research` | 启动研究 (同步) | JWT/Key |
| `POST` | `/ws/research/stream` | SSE 流式研究 | JWT/Key |
| `GET` | `/api/research/sessions` | 研究会话列表 | JWT/Key |
| `GET` | `/api/research/sessions/{id}` | 会话详情 | JWT/Key |
| `DELETE` | `/api/research/sessions/{id}` | 删除会话 | JWT/Key |
| `POST` | `/api/research/search` | 纯搜索 (无 LLM) | JWT/Key |
| `GET` | `/health` | 健康检查 | - |
| `GET` | `/metrics` | Prometheus 指标 | - |

## 数据库表结构

| 表 | 字段 | 用途 |
|------|------|------|
| `users` | id, username, hashed_password, api_key, is_active | 多租户认证 |
| `research_sessions` | id, user_id, topic, status, report_markdown, elapsed_ms | 研究会话 |
| `research_messages` | id, session_id, event_type, payload_json | SSE 事件日志 |
| `search_results` | id, session_id, query, backend, results_json | 搜索缓存 |
| `notes` | id, user_id, note_uid, title, content, note_type | 笔记持久化 |
| `source_cache` | id, url_hash, url, content, ttl_seconds | 跨会话页面缓存 |
| `usage_logs` | id, user_id, session_id, event, metadata_json | 用量审计 |

## 项目结构

```
langgraph-deepresearch/
├── backend/
│   ├── src/
│   │   ├── main.py               # FastAPI 入口 (CORS/Middleware/Lifespan)
│   │   ├── config.py             # 配置加载
│   │   ├── database.py           # SQLAlchemy async ORM
│   │   ├── models/
│   │   │   ├── db_models.py      # 7 张 ORM 表
│   │   │   └── schemas.py        # Pydantic 请求/响应
│   │   ├── api/
│   │   │   ├── auth.py           # JWT + API Key 认证
│   │   │   ├── research.py       # 研究 REST API
│   │   │   └── ws.py             # SSE 流式推送
│   │   ├── engine/
│   │   │   ├── orchestrator.py   # LangGraph StateGraph
│   │   │   ├── tool_calling.py   # 原生 Function Calling
│   │   │   └── context_guard.py  # 上下文溢出保护
│   │   ├── search/
│   │   │   ├── backends.py       # 6 种搜索后端 + 缓存
│   │   │   └── hybrid.py         # 多源融合排序
│   │   ├── memory/
│   │   │   ├── short_term.py     # 会话窗口记忆
│   │   │   └── long_term.py      # 跨会话持久记忆
│   │   ├── security/
│   │   │   ├── input_guard.py    # Prompt 注入检测
│   │   │   └── rate_limit.py     # 滑动窗口限流
│   │   ├── services/
│   │   │   ├── session.py        # 会话生命周期
│   │   │   └── observability.py  # 日志 + 指标
│   │   ├── agent.py              # DeepResearchAgent (兼容)
│   │   ├── agent_core.py         # SimpleAgent (兼容)
│   │   ├── prompts.py            # 系统提示词
│   │   ├── models.py             # 状态数据类 (保留)
│   │   ├── search_tools.py       # 原搜索工具 (保留)
│   │   └── note_tools.py         # 原笔记工具 (保留)
│   └── tests/
│       ├── conftest.py           # 测试基础设施
│       └── test_api.py           # API 集成测试
├── frontend/
│   └── src/
│       ├── main.ts               # Vue 入口 (Router + Pinia)
│       ├── App.vue               # 主组件
│       ├── router/index.ts       # 路由配置
│       ├── stores/research.ts    # Pinia 研究状态
│       ├── components/           # 15+ 子组件
│       └── services/api.ts       # SSE API 客户端
├── Dockerfile                    # 多阶段构建
├── docker-compose.yml            # 4 服务编排
├── .github/workflows/ci.yml     # CI/CD
└── README.md
```

## 技术栈

`FastAPI` `LangGraph` `Vue 3` `TypeScript` `SQLAlchemy` `SQLite` `JWT` `SSE` `Docker` `GitHub Actions` `Tavily` `DuckDuckGo` `SearXNG` `Perplexity` `Prometheus`

## 与原始项目对比

| 维度 | 原版 | 升级后 |
|------|------|--------|
| 认证 | 无 | JWT + API Key |
| 数据库 | 文件系统笔记 | SQLite 7 张表 |
| 测试 | 0 | 12+ |
| 搜索源 | 3 (perplexity 空壳) | 6 (含融合) |
| 工具调用 | `[TOOL_CALL]` 文本解析 | 原生 Function Calling |
| 编排 | 手动 while 循环 | LangGraph StateGraph |
| 前端 | 单文件 2300 行 | Router + Pinia + 组件 |
| 部署 | 手动 | Docker Compose |
| CI/CD | 无 | GitHub Actions |
| 可观测性 | print/loguru | 结构化 JSON + Metrics |
