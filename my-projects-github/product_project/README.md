# 🏭 产品级 AI Agent 项目集

五个从原型到部署的全链路生产级 AI Agent 平台，覆盖多 Agent 协作、深度研究、RAG 检索、通用 Agent 服务等核心方向。

---

## 项目总览

| # | 项目 | 定位 | 核心技术 | 升级层级 |
|:--:|------|------|------|:--:|
| 1 | [**Coding Agent Pro**](AutoGen_software_team/) | 多 Agent 软件研发平台 | AutoGen · FastAPI · Streamlit · Docker | 9 层 |
| 2 | [**ClawBot**](agent-platform/) | 通用 AI Agent 服务平台 | 手写 Agent 循环 · FastAPI · Redis · Telegram | 10 层 |
| 3 | [**Deep Research**](langgraph-deepresearch/) | 生产级深度研究平台 | LangGraph · 6 搜索引擎 · Function Calling · Vue3 | 10 层 |
| 4 | [**RAG Agent Pro**](rag-agent/) | 企业级 RAG 知识助手 | BM25+语义混合检索 · FastAPI · Streamlit | 10 层 |

---

## 技术矩阵

| 能力 | Coding Agent | ClawBot | Deep Research | RAG Agent |
|------|:--:|:--:|:--:|:--:|
| 多 Agent 协作 | ✅ AutoGen | — | ✅ LangGraph | — |
| JWT + API Key 认证 | ✅ | ✅ | ✅ | ✅ |
| 数据库持久化 | SQLite | SQLite | SQLite (7表) | SQLite |
| SSE 流式推送 | ✅ | ✅ | ✅ | ✅ |
| 工具调用 | AutoGen Tool | 手写 Tool Registry | 原生 Function Calling | LangChain Tool |
| Prompt 注入检测 | ✅ | ✅ | ✅ | ✅ |
| 速率限制 | ✅ | ✅ | ✅ | ✅ |
| 记忆系统 | — | 短期+长期 | 短期+长期 | 短期+长期 |
| 前端 | Streamlit | Streamlit | Vue 3 + Pinia | Streamlit |
| Docker 部署 | ✅ | ✅ | ✅ | ✅ |
| CI/CD | ✅ | ✅ | ✅ | ✅ |
| 集成测试 | ✅ | ✅ | 10/10 | 10/10 |

---

## 快速启动

```bash
git clone https://github.com/pzqd9798/-ai-agent-projects.git
cd -ai-agent-projects/my-projects-github/product_project

# 选择一个项目，例如：
cd langgraph-deepresearch
cp backend/.env.example backend/.env   # 填入 API Key
docker-compose up -d
```

---

## 面试展示建议

- **架构设计能力** → Deep Research（LangGraph 编排 + 6 后端搜索融合）
- **安全防护意识** → ClawBot（三层护栏 + 注入检测 + 速率限制）
- **全栈能力** → Deep Research（FastAPI + Vue3 + Pinia + Docker）
- **多 Agent 系统** → Coding Agent（AutoGen PM→Engineer→Reviewer 协作）
- **检索增强生成** → RAG Agent（BM25 + 语义混合检索 + 多知识库）

---

## License

MIT
