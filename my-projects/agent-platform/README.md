# 🤖 ClawBot — 企业级 AI Agent 服务平台

**一键部署、开箱即用**。从代码助手到智能客服，30 秒启动。

## 核心特性

- 📦 **场景模板** — 预置代码助手、智能客服、文档问答，选模板即可用
- 🎛️ **管理后台** — Web Dashboard：Agent 管理、用户管理、API Key、用量统计
- 🔄 **Agent 核心循环** — while True + stop_reason + 工具调度（手写，不依赖 LangChain）
- 🌐 **多通道接入** — REST API + SSE 流式 + Telegram Bot + Web UI
- 🧠 **双记忆系统** — 短期对话记忆（Redis）+ 长期向量记忆
- 🛡️ **三层安全护栏** — 输入注入检测、输出敏感信息脱敏、工具权限控制
- 🔧 **可扩展工具** — bash、文件读写、网页获取、浏览器自动化（可选）
- 🗜️ **上下文保护** — 3 阶段溢出重试（截断→LLM 压缩→报错）
- 🐳 **Docker 一键部署** — `docker-compose up -d`

## 30 秒启动

```bash
git clone https://github.com/pzqd9798/-ai-agent-projects.git
cd -ai-agent-projects/my-projects/agent-platform
cp .env.example .env
# 编辑 .env 填入 ANTHROPIC_API_KEY
docker-compose up -d
# 打开 http://localhost:8000
```

## 页面

| URL | 说明 |
|-----|------|
| `/` | 产品首页 |
| `/admin` | 管理后台 (默认密码: admin/admin123) |
| `/docs` | Swagger API 文档 |
| `/health` | 健康检查 |

## 预置模板

| 模板 | 工具 | 场景 |
|------|------|------|
| 💻 代码助手 | bash, read_file, write_file, web_fetch | 代码审查、调试、重构 |
| 🎧 智能客服 | web_fetch | 企业客服、知识库问答 |
| 📚 文档问答 | read_file, web_fetch | RAG 检索增强生成 |

## API

```bash
# 从管理后台生成 API Key，然后:
curl -X POST http://localhost:8000/agent \
  -H "Content-Type: application/json" \
  -H "X-API-Key: clawbot-xxxxx" \
  -d '{"message": "解释Python装饰器"}'
```

## 技术栈

Python 3.11+ · FastAPI · SQLite · Redis · Anthropic Claude · Docker · Streamlit

## License

MIT
