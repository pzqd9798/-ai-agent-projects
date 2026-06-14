"""RAG 知识助手 — 检索增强生成 Agent.

用法:
    # 索引文档
    python -m rag_agent ingest docs/ --dir

    # 交互式问答
    python -m rag_agent query -l memory.json -s memory.json

    # Web UI
    streamlit run rag_agent/ui.py

    # Python API
    from rag_agent.agent import RAGAgent
    agent = RAGAgent()
    agent.ingest_file("doc.pdf")
    response = agent.query("文档讲了什么？")
"""

from .cli import main

if __name__ == "__main__":
    main()
