# Agent Platform

**生产级 AI Agent 平台** — 从原型到部署的全链路实践项目。

## 核心特性

- 🔄 **Agent 核心循环** — while True + stop_reason + 工具调度（手写，不依赖 LangChain）
- 🌐 **多通道接入** — REST API + Telegram Bot + Web UI 三通道，统一 InboundMessage 抽象
- 🧠 **双记忆系统** — 短期对话记忆（Redis）+ 长期向量记忆
- 🛡️ **三层安全护栏** — 输入注入检测、输出敏感信息脱敏、工具权限控制
- 🔧 **可扩展工具** — bash、文件读写、网页获取、浏览器自动化（可选）
- 📦 **会话持久化** — JSONL 追加存储，支持跨重启恢复
- 🗜️ **上下文保护** — 3 阶段溢出重试（截断→LLM 压缩→报错）
- 📊 **FastAPI 服务化** — 同步 + SSE 流式端点，自动 OpenAPI 文档
- 🎨 **Streamlit Web UI** — 聊天界面 + 会话管理 + 安全状态面板
- 🐳 **容器化部署** — Docker 多阶段构建 + docker-compose（含 Redis）

## 架构

```
+------------------------ Agent Platform ------------------------+
|                                                                 |
|  Streamlit UI  ←→  FastAPI REST  ←→  Telegram Bot              |
|         |               |               |                       |
|         +-------+-------+-------+-------+                       |
|                 |               |                               |
|          InboundMessage   InboundMessage                        |
|                 |               |                               |
|            +----v---------------v----+                          |
|            |      Gateway Router     |  5级路由绑定              |
|            +------------+------------+                          |
|                         |                                       |
|            +------------v------------+                          |
|            |      Security Guard     |  输入/输出/工具三层       |
|            +------------+------------+                          |
|                         |                                       |
|            +------------v------------+                          |
|            |     Agent Engine        |  while True + stop_reason|
|            |  + Tool Registry        |  TOOLS + TOOL_HANDLERS   |
|            |  + Context Guard        |  3阶段溢出重试            |
|            |  + Session Store        |  JSONL 持久化             |
|            +-------------------------+                          |
|                         |                                       |
|       +--------+--------+--------+--------+                     |
|       |        |        |        |        |                     |
|    bash   read/write  web_fetch  browse  memory                 |
|       |        |        |        |        |                     |
|       +--------+--------+--------+--------+                     |
|                         |                                       |
|               Short-term Memory (Redis)                         |
|               Long-term Memory (Vector)                         |
+-----------------------------------------------------------------+
```

## 快速开始

### 1. 安装依赖

```bash
cd agent-platform
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env: 填入 ANTHROPIC_API_KEY
```

### 2. 运行 FastAPI 服务

```bash
python -m app.main
# 访问 http://localhost:8000/docs 查看 API 文档
```

### 3. 测试 Agent

```bash
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -d '{"message": "搜索Python最新版本"}'
```

### 4. 启动 Web UI

```bash
streamlit run app/ui/streamlit_app.py
```

### 5. Docker 部署

```bash
docker-compose up -d
```

## 项目结构

```
agent-platform/
├── app/
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置加载
│   ├── engine/                  # 核心引擎
│   │   ├── agent_loop.py        # Agent 核心循环
│   │   ├── tool_registry.py     # 工具注册分发
│   │   ├── context_guard.py     # 上下文溢出保护
│   │   └── session_store.py     # JSONL 会话持久化
│   ├── gateway/                 # 通道路由
│   │   ├── router.py            # 路由绑定
│   │   ├── rest_channel.py      # REST 通道
│   │   └── telegram_channel.py  # Telegram 通道
│   ├── tools/                   # 工具集
│   │   ├── builtin.py           # 内置工具 (bash, 文件, 网页)
│   │   └── browser_tool.py      # 浏览器自动化
│   ├── memory/
│   │   └── dual_memory.py       # 双记忆系统
│   ├── security/
│   │   └── guard.py             # 安全护栏
│   ├── intelligence/
│   │   └── soul.py              # 提示词组装
│   └── ui/
│       └── streamlit_app.py     # Web UI
├── workspace/
│   ├── prompts/                 # 系统提示词片段
│   └── .sessions/               # 会话持久化目录 (自动创建)
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 技术栈

- Python 3.11+ · FastAPI · Streamlit · Redis
- Anthropic Claude API · browser-use (可选)
- Docker · docker-compose

## License

MIT
