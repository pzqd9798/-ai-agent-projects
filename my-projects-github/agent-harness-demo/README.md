# Agent Harness Demo

> **一个可调试、可扩展的 Agent 运行框架演示项目**
>
> Agent = Model（智能） + Harness（框架）
> 你不是在写 AI，你是在搭一个"世界"让 AI 在里面工作。

---

## 📖 这是什么？

这是一个 **Agent Harness（代理运行框架）的最小实现**。它基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) 的 s01-s02 架构，在核心循环之上增加了**分级调试日志**、**会话录制**和**失败记录**能力，让你能直观地看到 Agent 内部每一步的执行过程。

### 核心架构

```
┌──────────────────────────────────────────────────────┐
│                    run.py (CLI入口)                    │
├──────────────────────────────────────────────────────┤
│                                                      │
│   ┌──────────┐     ┌──────────────┐                  │
│   │  User    │────▶│  Agent Loop  │                  │
│   │  Query   │     │  (core.py)   │                  │
│   └──────────┘     └──┬───┬───┬──┘                  │
│                       │   │   │                      │
│              ┌────────┘   │   └────────┐             │
│              ▼            ▼            ▼             │
│        ┌─────────┐ ┌──────────┐ ┌──────────┐        │
│        │ tools.py│ │logger.py │ │session.py│        │
│        │ 5 tools │ │5 levels  │ │recording │        │
│        │ +dispatch│ │TRACE→ERR │ │+ replay │        │
│        └─────────┘ └──────────┘ └──────────┘        │
│                                                      │
│   while stop_reason == "tool_use":                   │
│       response = LLM(messages, tools)                │
│       execute tools via Dispatch Map                 │
│       feed results back → loop                       │
└──────────────────────────────────────────────────────┘
```

**核心理念**：
- **循环不变** — `while True` 是唯一控制流，模型决定何时停止
- **开闭原则** — 加工具只需修改 `tools.py`，循环代码零改动
- **分层调试** — TRACE / DEBUG / INFO / WARN / ERROR 五级日志

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd agent-harness-demo
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 方式 A: 创建本地 .env 文件
cp .env.example .env
# 编辑 .env，填入你的 ANTHROPIC_API_KEY 和 MODEL_ID

# 方式 B: 复用父项目的 .env（learn-claude-code）
# 程序会自动向上查找 .env 文件
```

**支持的模型提供商**（Anthropic 兼容接口）：

| 提供商 | MODEL_ID | 价格 |
|--------|----------|------|
| Anthropic | `claude-sonnet-4-6` | 标准 |
| **DeepSeek** | `deepseek-chat` | ¥0.5/百万token |
| MiniMax | `MiniMax-M2.5` | 中等 |
| Kimi | `kimi-k2.5` | 中等 |

> 💡 学习阶段建议用 DeepSeek，最便宜，效果也够好。

### 3. 运行

```bash
# 普通模式 — 只显示关键步骤
python run.py

# 调试模式 — 显示工具调用详情和 token 消耗
python run.py --debug

# 追踪模式 — 显示原始 API 请求/响应
python run.py --trace

# 限制最大循环步数
python run.py --max-steps 5
```

### 4. 试试这些任务

```
harness >> Create a file called hello.py that prints "Hello, Agent!"
harness >> What files are in the current directory?
harness >> Run hello.py and show me the output
harness >> Read the contents of hello.py and explain it
```

---

## 🎛️ 交互命令

在 REPL 中输入以下命令：

| 命令 | 功能 |
|------|------|
| `q` / `exit` | 退出（自动保存会话记录） |
| `:stats` | 显示当前会话统计 |
| `:save [文件名]` | 手动保存会话记录 |
| `:debug` | 切换到 DEBUG 日志级别 |
| `:trace` | 切换到 TRACE 日志级别 |
| `:info` | 切回 INFO 日志级别 |
| `:help` | 显示帮助 |

---

## 📊 示例：一次完整的对话

### 输入
```
harness >> Create a file hello.py that prints "Hello, Agent!"
```

### 输出（INFO 模式）
```
13:25:01 ◆ STEP 1 — Calling model...
13:25:01 STEP 1  INFO  Step 1 tokens — in: 1,234 | out: 56 | total: 1,290
13:25:02 STEP 1  DEBUG Executing: write_file
13:25:02 STEP 1  INFO  Step 1 complete — 1 tool(s) executed

13:25:03 ◆ STEP 2 — Calling model...
13:25:03 STEP 2  INFO  Step 2 tokens — in: 1,345 | out: 89 | total: 1,434
13:25:03 STEP 2  INFO  Model stopped: end_turn

I've created `hello.py` with a function that prints "Hello, Agent!".
```

### 输出（DEBUG 模式，多更多细节）
```
13:25:01 ◆ STEP 1 — Calling model...
────────────────────────────────────────────────────────────
13:25:01 STEP 1  INFO  Step 1 tokens — in: 1,234 | out: 56 | total: 1,290
13:25:02 DEBUG Executing: write_file
  ├─ Tool: write_file
  │  Params: {'path': 'hello.py', 'content': 'print("Hello, Agent!")'}
  └─ Result: Wrote 28 bytes to hello.py
13:25:02 STEP 1  INFO  Step 1 complete — 1 tool(s) executed
...
```

---

## 🧩 项目结构

```
agent-harness-demo/
├── run.py                     # 交互式 CLI 入口
├── agent_harness/
│   ├── __init__.py            # 包说明
│   ├── core.py                # 核心循环 (agent_loop)
│   ├── tools.py               # 工具定义 + Dispatch Map
│   ├── logger.py              # 5 级调试日志
│   └── session.py             # 会话录制 & 回放
├── examples/
│   ├── 01_create_file.md      # 示例：创建文件
│   ├── 02_multi_step.md       # 示例：多步骤任务
│   └── 03_failure_cases.md    # 失败记录 & 边界情况
├── transcripts/               # 自动保存的会话记录
├── README.md                  # 本文件
├── requirements.txt           # 依赖
└── .env.example               # 配置模板
```

### 各模块职责

| 模块 | 行数 | 核心职责 |
|------|------|----------|
| `core.py` | ~100 | **Agent Loop** — `while stop_reason == "tool_use"` 循环，不改动 |
| `tools.py` | ~200 | **工具系统** — 5 个工具 + Dispatch Map + 安全沙箱 |
| `logger.py` | ~110 | **调试日志** — 5 级彩色输出，TRACE→ERROR |
| `session.py` | ~170 | **会话录制** — 记录每步、每工具、每错误，自动保存 |
| `run.py` | ~200 | **CLI 入口** — 参数解析、REPL、元命令处理 |

---

## 🐛 调试功能

### 日志级别说明

| 级别 | 触发方式 | 显示内容 |
|------|----------|----------|
| **INFO** | 默认 | 步骤标记、token 统计、模型停止原因 |
| **DEBUG** | `--debug` / `:debug` | 以上 + 工具调用参数、返回值预览、耗时 |
| **TRACE** | `--trace` / `:trace` | 以上 + 原始 API 响应、完整工具输出 |
| **WARN** | 自动 | 工具执行失败、危险命令拦截 |
| **ERROR** | 自动 | API 调用失败、循环异常退出 |

### 会话录制

每次运行结束后，会在 `transcripts/` 目录自动保存一份完整的 Markdown 会话记录，包含：
- 用户的所有输入
- 每一步的 token 消耗和耗时
- 每次工具调用的参数和返回值
- 所有错误和警告

---

## 🔧 扩展指南

### 添加新工具（4 步）

以添加 `web_search` 工具为例：

**1. 在 `tools.py` 中实现处理函数**：
```python
def run_web_search(query: str) -> dict:
    # 实现搜索逻辑
    try:
        results = some_search_api(query)
        return {"ok": True, "output": str(results)}
    except Exception as e:
        return {"ok": False, "output": f"[ERROR] {e}"}
```

**2. 在 `TOOLS` 列表中增加工具定义**：
```python
{
    "name": "web_search",
    "description": "Search the web for information.",
    "input_schema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
},
```

**3. 在 `TOOL_HANDLERS` 中注册**：
```python
TOOL_HANDLERS = {
    # ... existing handlers ...
    "web_search": run_web_search,
}
```

**4. 完成！** 循环代码 (`core.py`) 和 CLI (`run.py`) **不需要任何修改**。这是 Dispatch Map 模式的核心优势。

---

## 📝 学习要点

这个 Demo 展示了以下关键概念：

1. **Agent 的本质**
   - Agent ≠ 智能模型
   - Agent = 模型（智能） + Harness（框架）
   - Harness 的职责：给模型提供**工具**、**边界**和**记忆**

2. **Dispatch Map 模式**
   - 工具注册与执行解耦
   - 加工具不改循环（开闭原则）
   - 这是生产级 Agent 框架的基础

3. **调试与可观测性**
   - 分级日志让你逐级深入
   - 会话录制让你事后复盘
   - 失败记录帮你定位边界情况

4. **安全边界**
   - `safe_path()` 阻止路径逃逸
   - `run_bash()` 拦截危险命令模式
   - 生产环境中这些会替换为真正的沙箱

---

## 📄 License

MIT — 基于 learn-claude-code 项目的学习产出。
