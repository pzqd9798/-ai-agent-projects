# 🤖 AI Agent 项目集

> 彭子琪的 AI Agent 全栈项目集 — 从核心原理到生产部署的完整实践

---

## 📂 项目结构

```
-ai-agent-projects/
├── my-projects-github/          ← 主体项目
│   ├── product_project/         ★ 4 个产品级项目（10层全链路）
│   ├── agent-harness-demo/      Agent 运行框架演示
│   ├── daily-digest/            信息聚合日报
│   ├── job-agent/               自动化求职助手
│   ├── langgraph-trip-planner/  LangGraph 旅行规划
│   ├── release-note-writer/     Release Note 自动生成
│   └── web-agent/               智能网页信息采集
└── my_project_learn/            ← 学习笔记
```

---

## 🏭 产品级项目（product_project）

> 全部完成 10 层生产级升级：认证 → 数据库 → 测试 → 编排 → 工具调用 → 搜索增强 → 流式可观测 → 记忆系统 → 前端重构 → DevOps

| 项目 | 定位 | 核心技术 | 亮点 |
|------|------|------|------|
| [**ClawBot**](my-projects-github/product_project/agent-platform/) | 通用 AI Agent 服务平台 | FastAPI · Streamlit · Redis · Telegram | 手写 Agent 循环，不依赖 LangChain |
| [**Deep Research**](my-projects-github/product_project/langgraph-deepresearch/) | 生产级深度研究平台 | LangGraph · 6 搜索引擎 · Vue 3 | Function Calling · 7表 ORM · 10/10 测试 |
| [**Coding Agent Pro**](my-projects-github/product_project/AutoGen_software_team/) | 多 Agent 软件研发平台 | AutoGen · FastAPI · Docker | PM→Engineer→Reviewer 协作流水线 |
| [**RAG Agent Pro**](my-projects-github/product_project/rag-agent/) | 企业级 RAG 知识助手 | FastAPI · Streamlit · SQLite | BM25+语义混合检索 · 双记忆 |

---

## 🛠️ 工具 & Demo 项目

| 项目 | 说明 | 技术栈 |
|------|------|--------|
| [agent-harness-demo](my-projects-github/agent-harness-demo/) | Agent 运行框架（Model + Harness 解耦） | Python · JSONL 会话持久化 |
| [langgraph-trip-planner](my-projects-github/langgraph-trip-planner/) | LangGraph 旅行规划助手（并行搜索+校验） | LangGraph StateGraph · 高德 API |
| [web-agent](my-projects-github/web-agent/) | 智能网页信息采集 + LLM 摘要 | BeautifulSoup · browser-use |
| [job-agent](my-projects-github/job-agent/) | 自动化求职：搜索 + 简历匹配 | browser-use · LLM |
| [daily-digest](my-projects-github/daily-digest/) | 多源信息聚合日报 + Telegram 推送 | Hacker News · GitHub · RSS |
| [release-note-writer](my-projects-github/release-note-writer/) | Release Note 自动生成模板 | Markdown · CLI |

---

## 🔧 技术矩阵

| 能力 | Deep Research | ClawBot | Coding Agent | RAG Agent |
|------|:--:|:--:|:--:|:--:|
| 多 Agent 编排 | LangGraph | 手写循环 | AutoGen | — |
| JWT + API Key | ✅ | ✅ | ✅ | ✅ |
| 数据库 (SQLite) | 7 表 | 用户/会话 | 项目/版本 | 文档/知识库 |
| SSE 流式 | ✅ | ✅ | ✅ | ✅ |
| Function Calling | 原生 | Tool Registry | AutoGen Tool | LangChain |
| 搜索增强 | 6 后端+融合 | — | — | BM25+语义 |
| Prompt 注入检测 | ✅ | ✅ | ✅ | ✅ |
| 双记忆系统 | ✅ | ✅ | — | ✅ |
| 前端框架 | Vue 3 + Pinia | Streamlit | Streamlit | Streamlit |
| Docker Compose | ✅ | ✅ | ✅ | ✅ |
| CI/CD | GitHub Actions | ✅ | ✅ | ✅ |
| 集成测试 | 10/10 | ✅ | ✅ | 10/10 |

---

## 🚀 快速启动

```bash
git clone https://github.com/pzqd9798/-ai-agent-projects.git
cd -ai-agent-projects/my-projects-github/product_project

# 以 Deep Research 为例
cd langgraph-deepresearch
cp backend/.env.example backend/.env   # 填入 LLM_API_KEY
docker-compose up -d                   # API → http://localhost:8000/docs
```

---

## 📋 技能体系

| 领域 | 具体技能 |
|------|------|
| **Agent 框架** | LangGraph, AutoGen, 手写 Agent 循环 |
| **后端** | FastAPI, Flask, Python, TypeScript |
| **前端** | Vue 3, Vite, Streamlit, Ant Design Vue |
| **LLM** | Anthropic Claude, DeepSeek, OpenAI, Ollama |
| **Agent 核心** | RAG, MCP, A2A, Prompt Engineering, Tool Use, Memory, Function Calling |
| **安全** | JWT, API Key, Prompt Injection Guard, Rate Limiting |
| **DevOps** | Docker, Docker Compose, GitHub Actions CI/CD |
| **数据库** | SQLAlchemy, aiosqlite, Redis |
| **可观测** | JSON 结构化日志, Prometheus Metrics, SSE 流式 |

---

## License

MIT
