# 深度研究助手

基于 LangGraph 的多 Agent 深度研究系统。3 个 Agent 分工协作，集成 4 个搜索引擎，TODO 驱动研究流程，前端 Vue3 展示。

## 架构

```
用户输入研究主题
    │
    ▼
研究规划专家 → 拆解主题为 3~5 个子任务
    │
    ▼
搜索专家 → 逐任务搜索（Tavily / DuckDuckGo / SearXNG）
    │
    ▼
总结专家 → 整合结果，提炼关键信息
    │
    ▼
报告撰写专家 → 生成结构化 Markdown 报告
```

## 核心特性

- 3 Agent 协作：规划 → 搜索 → 撰写
- 4 搜索引擎集成，支持灵活切换与降级
- TODO 驱动流程，NoteTool 持久化进度，支持断点续研
- SSE 流式推送研究进度
- 多 LLM 后端（OpenAI / Ollama / LMStudio）

## 快速开始

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python run.bat
```

## 技术栈

`LangGraph` `FastAPI` `Vue3` `TypeScript` `Tavily` `DuckDuckGo` `SearXNG` `SSE`
