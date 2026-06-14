# 📚 RAG Agent Pro

**企业级检索增强生成 (RAG) 知识助手平台**

> 文档摄取 → 向量索引 → 混合检索 → 增强生成
> BM25 + 语义 · 多知识库 · 双记忆 · 流式输出 · Docker 部署

---

## 架构

```
┌─ Streamlit 前端 ──┐     ┌── FastAPI 后端 ─────────────┐
│  frontend/app.py   │────▶│  app/main.py                │
│                    │     │                             │
│  知识库管理 · 对话  │     │  /api/auth       JWT 认证   │
│  文档上传 · 搜索    │     │  /api/knowledge  知识库CRUD │
│  SSE 流式           │◀────│  /api/chat       RAG 问答   │
└────────────────────┘     │  /api/documents   文档管理  │
                           │  /ws/chat/stream  SSE 流式  │
                           │                             │
                           │  engine/                    │
                           │  ├── rag_pipeline.py  RAG管道│
                           │  ├── embedder.py  向量嵌入  │
                           │  ├── hybrid_search.py BM25  │
                           │  └── chunker.py   文本分块  │
                           │                             │
                           │  services/                  │
                           │  ├── ingestion.py   文档摄取 │
                           │  ├── memory_service.py 记忆  │
                           │  └── observability.py 日志   │
                           │                             │
                           │  worker/tasks.py  arq 队列  │
                           └──────────┬──────────────────┘
                                      │
                            ┌─────────┴──────────┐
                            │  SQLite · Redis      │
                            └────────────────────┘
```

---

## 快速开始

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY

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
rag-agent/
├── backend/
│   ├── app/
│   │   ├── main.py               FastAPI 入口
│   │   ├── config.py             配置管理
│   │   ├── database.py           SQLite 异步访问 (8 张表)
│   │   ├── api/                  API 路由
│   │   │   ├── auth.py           JWT + API Key 认证
│   │   │   ├── knowledge.py      知识库 CRUD
│   │   │   ├── chat.py           RAG 问答 + 会话管理
│   │   │   ├── documents.py      文档上传 + 纯检索
│   │   │   └── ws.py             SSE 流式输出
│   │   ├── engine/               RAG 引擎
│   │   │   ├── rag_pipeline.py   检索→增强→生成 管道
│   │   │   ├── embedder.py       Voyage/OpenAI/TF-IDF 嵌入器
│   │   │   ├── hybrid_search.py  BM25 + 向量混合检索
│   │   │   └── chunker.py        自适应文本分块
│   │   ├── models/
│   │   │   └── schemas.py        Pydantic 模型
│   │   ├── services/             业务服务
│   │   │   ├── ingestion.py      文档摄取管道
│   │   │   ├── memory_service.py 双记忆系统
│   │   │   └── observability.py  日志 + 指标
│   │   └── worker/
│   │       └── tasks.py          arq 异步任务
│   ├── tests/
│   │   └── test_api.py           API 集成测试
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── app.py                    Streamlit 5 页前端
├── rag_agent/                    原版纯 Python SDK (保留)
│   ├── agent.py
│   ├── ingestion.py
│   ├── memory.py
│   ├── vector_store.py
│   ├── ui.py
│   └── cli.py
├── docker-compose.yml
├── start.py                      启动脚本
├── .env.example
└── README.md
```

---

## 10 层生产级升级

| # | 层级 | 实现 | 文件 |
|:--:|------|------|------|
| 1 | **后端分离** | FastAPI 路由层，前后端 HTTP 通信 | `main.py` + `api/` |
| 2 | **多租户认证** | JWT + API Key 双认证，知识库隔离 | `api/auth.py` |
| 3 | **持久化** | SQLite + aiosqlite, 8 张表 | `database.py` |
| 4 | **异步任务** | arq + Redis，大文件不阻塞请求 | `worker/tasks.py` |
| 5 | **知识库管理** | 多知识库 CRUD、标签、统计 | `api/knowledge.py` |
| 6 | **真实 Embedding** | Voyage AI / OpenAI 兼容 / TF-IDF 降级 | `engine/embedder.py` |
| 7 | **混合检索** | BM25 关键词 + 向量语义加权融合 | `engine/hybrid_search.py` |
| 8 | **流式输出** | SSE 实时 token 推送 | `api/ws.py` |
| 9 | **可观测性** | 结构化日志 + 指标采集 + 健康检查 | `services/observability.py` |
| 10 | **Docker 部署** | Compose 一键启动 4 个服务 | `docker-compose.yml` |

---

## 数据库表

| 表名 | 说明 | 关键字段 |
|------|------|------|
| `users` | 用户 | username, password_hash, api_key, role |
| `knowledge_bases` | 知识库 | user_id, name, description, tags |
| `documents` | 文档 | kb_id, filename, format, status |
| `chunks` | 文本片段 | doc_id, text, chunk_index, embedding |
| `chat_sessions` | 对话会话 | user_id, kb_id, title |
| `chat_messages` | 聊天记录 | session_id, role, content, sources |
| `user_memories` | 长期记忆 | user_id, memory_type, key, value |
| `usage_logs` | 用量日志 | user_id, kb_id, action, tokens_used |

---

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| GET | `/api/auth/me` | 当前用户信息 |
| POST | `/api/knowledge` | 创建知识库 |
| GET | `/api/knowledge` | 知识库列表 |
| GET | `/api/knowledge/{id}` | 知识库详情 |
| PUT | `/api/knowledge/{id}` | 更新知识库 |
| DELETE | `/api/knowledge/{id}` | 删除知识库 |
| POST | `/api/documents/upload` | 上传文档 |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| POST | `/api/documents/search` | 纯语义检索 |
| POST | `/api/chat` | RAG 问答 |
| GET | `/api/chat/sessions` | 会话列表 |
| GET | `/api/chat/sessions/{id}/messages` | 会话消息 |
| DELETE | `/api/chat/sessions/{id}` | 删除会话 |
| GET | `/ws/chat/stream` | SSE 流式问答 |
| GET | `/health` | 健康检查 |

---

## 技术栈

- **Web 框架**: FastAPI + Uvicorn
- **数据库**: SQLite + SQLAlchemy (async) + aiosqlite
- **任务队列**: arq + Redis
- **认证**: JWT (python-jose) + bcrypt
- **LLM**: Anthropic Claude API
- **Embedding**: Voyage AI / OpenAI 兼容 / TF-IDF 本地
- **检索**: BM25 + 余弦相似度混合融合
- **文档解析**: PyPDF + markdown-it-py
- **前端**: Streamlit
- **部署**: Docker Compose

---

## 与市场产品的对比

| 能力 | RAG Agent Pro | ChatGPT Retrieval | Cohere | LlamaIndex |
|------|:--:|:--:|:--:|:--:|
| 混合检索 (BM25+向量) | ✅ | ❌ | ✅ | ✅ |
| 多知识库隔离 | ✅ | ❌ | ❌ | ✅ |
| 多租户认证 | ✅ | ❌ | ❌ | ❌ |
| SSE 流式 | ✅ | ✅ | ✅ | ❌ |
| 双记忆系统 | ✅ | ❌ | ❌ | ❌ |
| API 化 | ✅ | ❌ | ✅ | ❌ |
| Web UI | ✅ | ✅ | ❌ | ❌ |
| Docker 一键部署 | ✅ | ❌ | ❌ | ❌ |
| 离线降级 (TF-IDF) | ✅ | ❌ | ❌ | ❌ |

---

## License

MIT
