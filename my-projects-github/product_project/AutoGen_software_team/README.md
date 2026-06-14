# 🤖 Coding Agent Pro

**基于 AutoGen 多 Agent 协作的生产级软件研发平台**

> ProductManager → Engineer → CodeReviewer → UserProxy
> 三阶段流程 · 模板市场 · 版本历史 · 代码沙箱 · 流式输出

---

## 架构

```
┌─ Streamlit 前端 ──┐     ┌── FastAPI 后端 ──────────────┐
│  frontend/app.py   │────▶│  app/main.py                 │
│                    │     │                              │
│  项目管理 · 工作区  │     │  /api/auth    JWT 认证       │
│  模板浏览 · 版本历史│     │  /api/projects  项目 CRUD    │
│  WebSocket 流式     │◀────│  /api/projects/{id}/phases   │
└────────────────────┘     │  /api/projects/{id}/versions  │
                           │  /ws/.../{id}/stream  SSE    │
                           │                              │
                           │  engine/                     │
                           │  ├── agent_runner.py AutoGen  │
                           │  ├── templates.py  模板市场   │
                           │  └── sandbox.py    Docker沙箱 │
                           │                              │
                           │  services/                   │
                           │  ├── versioning.py  版本历史  │
                           │  └── observability.py 日志    │
                           │                              │
                           │  worker/tasks.py  arq 队列   │
                           └──────────┬───────────────────┘
                                      │
                            ┌─────────┴──────────┐
                            │  SQLite · Redis     │
                            │  Docker Sandbox     │
                            └────────────────────┘
```

---

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 2. 安装依赖
pip install -r backend/requirements.txt

# 3. 启动后端
python start.py

# 4. (新终端) 启动前端
streamlit run frontend/app.py
```

访问:
- **API 文档**: http://localhost:8000/docs
- **Streamlit 前端**: http://localhost:8501

---

## Docker 部署

```bash
# 一键启动 (API + Redis)
docker-compose up -d

# 全栈模式 (API + Redis + Worker + Streamlit)
docker-compose --profile full up -d
```

---

## 项目结构

```
AutoGen_software_team/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI 入口
│   │   ├── config.py            配置管理
│   │   ├── database.py          SQLite 异步访问
│   │   ├── api/                 API 路由
│   │   │   ├── auth.py          JWT 认证
│   │   │   ├── projects.py      项目 CRUD
│   │   │   ├── phases.py        阶段执行
│   │   │   ├── versions.py      版本管理
│   │   │   └── ws.py            WebSocket 流式
│   │   ├── engine/              Agent 引擎
│   │   │   ├── agent_runner.py  AutoGen 封装
│   │   │   ├── templates.py     Agent 模板
│   │   │   └── sandbox.py       Docker 沙箱
│   │   ├── models/              Pydantic 模型
│   │   ├── services/            业务服务
│   │   │   ├── versioning.py    版本历史
│   │   │   └── observability.py 可观测性
│   │   └── worker/              异步任务
│   │       └── tasks.py         arq Worker
│   ├── tests/
│   │   └── test_api.py          API 集成测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── app.py                   Streamlit 前端
├── team/                        AutoGen 团队模块 (保留)
│   ├── agents.py
│   └── orchestrator.py
├── docker-compose.yml
├── start.py                     启动脚本
├── .env.example
└── README.md
```

---

## 9 层生产级升级

| # | 层级 | 实现 | 文件 |
|:--:|------|------|------|
| 1 | **后端分离** | FastAPI 路由层, 前后端 HTTP 通信 | `main.py` + `api/` |
| 2 | **异步任务** | arq + Redis, 长任务不阻塞 | `worker/tasks.py` |
| 3 | **持久化** | SQLite + aiosqlite, 7 张表 | `database.py` |
| 4 | **多租户** | JWT + API Key 双认证 | `api/auth.py` |
| 5 | **模板市场** | 3 套内置模板, 可扩展 | `engine/templates.py` |
| 6 | **代码沙箱** | Docker 容器隔离执行 | `engine/sandbox.py` |
| 7 | **版本历史** | Git 风格快照 + 差异对比 + 回退 | `services/versioning.py` |
| 8 | **可观测性** | 结构化日志 + Prometheus 指标 | `services/observability.py` |
| 9 | **Docker 部署** | Compose 一键启动 4 个服务 | `docker-compose.yml` |

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/projects` | 创建项目 |
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects/{id}/phases/plan` | 执行需求分析 |
| POST | `/api/projects/{id}/phases/code` | 执行代码生成 |
| POST | `/api/projects/{id}/phases/review` | 执行质量审查 |
| GET | `/api/projects/{id}/artifacts` | 获取产物 |
| POST | `/api/projects/{id}/versions` | 创建版本快照 |
| GET | `/api/projects/{id}/versions/diff` | 版本对比 |
| WS | `/ws/projects/{id}/stream` | WebSocket 流式 |
| GET | `/health` | 健康检查 |
