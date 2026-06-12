# My Projects

AI Agent 全栈项目实践，覆盖 Agent 核心原理、多框架应用、前后端开发、容器化部署。

---

## Projects

### ClawBot — AI Agent 服务平台

从零实现的 Agent 服务平台。手写 Agent 核心循环（while True + stop_reason + 工具分发表），包含 Web 管理后台、场景模板、多用户系统、上下文溢出保护、安全护栏、Docker 部署。

`FastAPI` `SQLite` `Redis` `Docker` `Streamlit` `Anthropic Claude`

→ [agent-platform](agent-platform/)

### 旅行规划助手 — LangGraph 多 Agent 协作

4 Agent 旅行规划系统。LangGraph 状态图编排，MCP 协议集成高德地图，Pydantic 强类型数据模型，Vue3 全栈前后端。

`LangGraph` `FastAPI` `Vue3` `TypeScript` `MCP` `高德地图API`

→ [langgraph-trip-planner](langgraph-trip-planner/)

### 深度研究助手 — 多引擎搜索 Agent

3 Agent 协作深度研究。TODO 驱动流程，集成 4 个搜索引擎（Tavily/DuckDuckGo/SearXNG），SSE 流式推送，Vue3 前端。

`LangGraph` `FastAPI` `Vue3` `TypeScript` `Tavily` `SSE`

→ [langgraph-deepresearch](langgraph-deepresearch/)

### AutoGen 软件研发团队 — 4 Agent 协作流水线

基于 Microsoft AutoGen 框架的软件研发团队。ProductManager → Engineer → CodeReviewer → UserProxy 自动协作。前后端分离。

`AutoGen` `FastAPI` `Streamlit` `DeepSeek`

→ [AutoGen_software_team](AutoGen_software_team/)

### RAG 知识助手 — 检索增强生成

从零实现 RAG 管道。文档摄取、自适应分块、TF-IDF 向量化、语义检索、LLM 增强生成。双记忆系统。

`Python` `Streamlit` `TF-IDF` `Redis` `Anthropic Claude`

→ [rag-agent](rag-agent/)

### 求职助手 — 浏览器自动化 + 简历匹配

browser-use 自动化职位搜索，LLM 多维度简历匹配评分。演示模式零依赖运行。

`browser-use` `Anthropic Claude`

→ [job-agent](job-agent/)

### 智能网页采集 — 双模提取 + AI 摘要

静态 HTTP 和浏览器双模网页内容提取，LLM 结构化摘要，批量并发处理。

`BeautifulSoup` `browser-use` `httpx`

→ [web-agent](web-agent/)

### 信息聚合日报 — 多源采集 + 定时推送

Hacker News、GitHub Trending、知乎热榜、RSS 多源采集。LLM 分类整理，cron 定时调度，Telegram 推送。

`feedparser` `Anthropic Claude` `Telegram API`

→ [daily-digest](daily-digest/)

### Agent Harness Demo — Agent 运行框架

Agent 核心循环 + 5 级调试日志 + 会话录制回放 + 安全沙箱。基于 learn-claude-code 架构扩展。

`Anthropic Claude` `Dispatch Map`

→ [agent-harness-demo](agent-harness-demo/)

### Release Note Writer — Claude Code Skill

从 git 提交历史自动生成结构化 Release Notes。包含模板系统、自动化验证脚本、烟雾测试对照实验。

`Claude Code Skill` `Shell` `Conventional Commits`

→ [release-note-writer](release-note-writer/)

---

## Skills

Agent 核心原理 · LangGraph · AutoGen · MCP 协议 · RAG · Tool Use · Prompt Engineering · FastAPI · Vue3 · Streamlit · Docker · 浏览器自动化 · 安全护栏

---

All projects at [github.com/pzqd9798/-ai-agent-projects](https://github.com/pzqd9798/-ai-agent-projects)
