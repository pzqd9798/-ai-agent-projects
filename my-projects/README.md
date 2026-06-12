# My Projects — AI Agent 全栈项目集

> 10 个自研项目 · ~12,000 行代码 · 覆盖 Agent 全链路

---

## 🥇 第一梯队（主打项目）

### 🤖 [ClawBot](agent-platform/) — 企业级 AI Agent 服务平台

从零设计开发，手写 Agent 核心循环，不依赖 LangChain。包含 Web 管理后台、3 个场景模板、多用户系统、三层安全护栏、双记忆架构、Docker 一键部署。

**技术**: FastAPI · SQLite · Redis · Docker · Streamlit · Anthropic Claude

### ✈️ [旅行规划助手](langgraph-trip-planner/) — LangGraph 多 Agent 协作

基于 LangGraph 状态图的 4 Agent 旅行规划系统。通过 MCP 协议集成高德地图 API 获取真实地理数据，Pydantic 强类型 Schema，Vue3 全栈前端。

**技术**: LangGraph · FastAPI · Vue3 · MCP · 高德地图 API · Unsplash

### 🔍 [深度研究助手](langgraph-deepresearch/) — 多 Agent 深度研究

3 Agent 分工协作（规划→搜索→撰写），集成 4 个搜索引擎，TODO 驱动研究流程，SSE 流式推送，Vue3 前端。

**技术**: LangGraph · FastAPI · Vue3 · Tavily · DuckDuckGo · SearXNG

---

## 🥈 第二梯队（辅助项目）

### 👨‍💻 [AutoGen 软件研发团队](AutoGen_software_team/) — 4 Agent 研发流水线

ProductManager → Engineer → CodeReviewer → UserProxy 自动协作。前后端分离（FastAPI + Streamlit），SSE 流式实时展示。

**技术**: AutoGen · FastAPI · Streamlit · DeepSeek

### 📚 [RAG 知识助手](rag-agent/) — 检索增强生成

从零实现完整 RAG 管道：文档摄取→分块→TF-IDF 向量化→语义检索→LLM 增强生成。双记忆系统。

**技术**: TF-IDF · Streamlit · Redis · Anthropic Claude

### 🎯 [求职助手](job-agent/) — 浏览器自动化 + 简历匹配

browser-use 自动搜索职位，LLM 7 维度简历匹配评分，演示模式零依赖运行。

**技术**: browser-use · Anthropic Claude · Rich

### 🌐 [智能网页采集](web-agent/) — 双模提取 + AI 摘要

静态 HTTP + 浏览器双模提取，LLM 结构化摘要，批量并发处理。

**技术**: BeautifulSoup · browser-use · httpx · Rich

### 📰 [信息聚合日报](daily-digest/) — 多源聚合 + 定时推送

Hacker News · GitHub Trending · 知乎热榜 · RSS 多源采集，LLM 分类整理，定时调度 + Telegram 推送。

**技术**: feedparser · Anthropic Claude · Telegram Bot API

---

## 🥉 第三梯队（加分项）

### ⚙️ [Agent Harness Demo](agent-harness-demo/) — Agent 运行框架

手写 Agent 循环 + 5 级调试日志 + 会话录制回放 + 安全沙箱。展示对 Agent 底层的理解。

**技术**: Anthropic Claude · Dispatch Map · Session Recording

### 📝 [Release Note Writer](release-note-writer/) — Claude Code Skill

从 git log 自动生成结构化 Release Notes。包含模板系统、验证脚本、A/B 对照实验。

**技术**: Claude Code Skill · Shell · Conventional Commits

---

## 技能覆盖

| 领域 | 深度 | 领域 | 深度 |
|------|:---:|------|:---:|
| Agent 核心原理 | 🟢 | FastAPI | 🟢 |
| LangGraph | 🟢 | Vue3/TypeScript | 🟡 |
| AutoGen | 🟡 | Streamlit | 🟢 |
| MCP 协议 | 🟢 | Docker | 🟢 |
| RAG/向量检索 | 🟢 | Git/GitHub | 🟢 |
| Prompt Engineering | 🟢 | 浏览器自动化 | 🟡 |
| Tool Use/Dispatch | 🟢 | 安全护栏 | 🟢 |

---

## GitHub

**所有项目**: https://github.com/pzqd9798/-ai-agent-projects
