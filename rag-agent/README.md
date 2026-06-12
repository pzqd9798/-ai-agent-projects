# RAG 知识助手 — 检索增强生成 Agent

具备双记忆系统的 RAG (Retrieval-Augmented Generation) 知识助手。上传文档 → 自动分块索引 → 语义检索 → LLM 增强生成。

## 核心特性

- 📄 **多格式文档摄取** — PDF, Markdown, TXT，自动分块和元数据提取
- 🔍 **语义检索** — TF-IDF 向量化 + 余弦相似度搜索 (零外部依赖)
- 🧠 **双记忆系统** — 短期对话流 (滑动窗口) + 长期记忆 (偏好/事实/会话摘要)
- 🤖 **RAG 管道** — 检索 → 增强上下文组装 → LLM 生成回答
- 🎨 **Streamlit Web UI** — 拖拽上传、实时问答、来源追溯
- 💾 **记忆持久化** — 长期记忆可保存/加载为 JSON
- 🔌 **Redis 可选** — 生产环境可切换到 Redis 向量存储

## 架构

```
用户问题
    |
    v
向量存储 (TF-IDF + Cosine)  ←──  文档摄取管道 (PDF/MD/TXT → 分块)
    |                                    |
    +──→ 增强上下文组装 ←── 长期记忆 (偏好/事实/历史)
              |
              +──→ LLM (Claude) → 回答
              |
        短期记忆 ←── 对话流
```

## 快速开始

```bash
cd rag-agent
pip install -r requirements.txt
cp .env.example .env
```

### Web UI

```bash
streamlit run rag_agent/ui.py
```

### CLI

```bash
# 索引文档
python -m rag_agent ingest docs/ --dir

# 交互式问答
python -m rag_agent query
```

### Python API

```python
from rag_agent.agent import RAGAgent

agent = RAGAgent()
agent.ingest_file("document.pdf")
response = agent.query("文档讲了什么？")
print(response.answer)
print(response.sources)
```

## 技术栈

- Python 3.11+ · Anthropic Claude API
- PyPDF · markdown-it-py
- Streamlit · Redis (可选)

## License

MIT
