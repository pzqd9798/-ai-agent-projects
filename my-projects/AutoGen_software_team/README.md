# AutoGen 软件研发团队

基于 **Microsoft AutoGen** 框架的 4 Agent 软件研发协作系统。ProductManager → Engineer → CodeReviewer → UserProxy 流水线，自然语言驱动端到端开发。

## 架构

```
用户任务 (自然语言)
    │
    ▼
┌─────────────────────────────────────────────┐
│         RoundRobinGroupChat (团队编排)        │
│                                              │
│  ProductManager   Engineer   CodeReviewer    │
│       │               │           │          │
│   需求分析         编码实现     代码审查       │
│   模块划分         技术选型     安全性检查     │
│   优先级排序       错误处理     改进建议       │
│       │               │           │          │
│       └───────────────┼───────────┘          │
│                       ▼                      │
│                   UserProxy                  │
│                (测试验证+终止)                │
└─────────────────────────────────────────────┘
    │
    ▼
  输出: 可运行代码 + 审查意见 + 协作记录
```

## 预设任务

| 任务 | 技术栈 | 产出 |
|------|--------|------|
| `bitcoin-tracker` | Streamlit + API | 比特币价格追踪 Web 应用 |
| `todo-api` | FastAPI + SQLite | RESTful Todo API 服务 |
| `markdown-blog` | Flask + Markdown | Markdown 个人博客系统 |

## 快速开始

### CLI 模式

```bash
cd AutoGen_software_team
pip install -r requirements.txt
cp .env.example .env  # 填入 LLM_API_KEY

python run.py                          # 默认: 比特币追踪器
python run.py --task todo-api          # Todo API 服务
python run.py --task "开发一个..."      # 自定义任务
python run.py --list                   # 列出预设任务
```

### 前后端分离模式

```bash
# 终端1: 启动 FastAPI 后端
python backend.py
# → http://localhost:8001

# 终端2: 启动 Streamlit 前端
streamlit run frontend.py
# → http://localhost:8501
```

前端界面支持：
- 预设任务下拉选择
- 自定义任务输入
- 实时流式展示团队对话（按角色颜色区分）
- 任务状态追踪

## Agent 角色设计

每个 Agent 的 system_message 明确定义了:
- 角色定位与职责
- 技术专长领域
- 工作流程步骤
- 对话引导（下一步由谁接手）

这样设计使得 Agent 行为可预测、可调试，而非黑盒 prompt。

## 技术栈

- **AutoGen AgentChat**: 多 Agent 协作框架
- **RoundRobinGroupChat**: 轮询编排策略
- **DeepSeek / OpenAI 兼容**: 模型后端
- **Streamlit / FastAPI / Flask**: 产出技术栈

## 项目结构

```
AutoGen_software_team/
├── team/
│   ├── agents.py          # Agent 定义 (可复用角色工厂)
│   └── orchestrator.py    # 模型创建 + 任务库 + 执行器
├── run.py                 # CLI 入口
├── output/                # 协作记录 (自动保存)
├── requirements.txt
└── README.md
```

## License

MIT
