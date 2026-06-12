"""Streamlit UI — RAG 知识助手交互界面.

启动方式: streamlit run rag_agent/ui.py
"""

import sys
import os
from pathlib import Path

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from rag_agent.agent import RAGAgent
from rag_agent.vector_store import InMemoryVectorStore


# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RAG 知识助手",
    page_icon="📚",
    layout="wide",
)

st.title("📚 RAG 知识助手")
st.caption("检索增强生成 — 上传文档，提问，获得基于知识的回答")

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

if "agent" not in st.session_state:
    redis_url = os.getenv("REDIS_URL", "")
    st.session_state.agent = RAGAgent(redis_url=redis_url)
    st.session_state.messages = []

agent: RAGAgent = st.session_state.agent

# ---------------------------------------------------------------------------
# 侧边栏 — 文档管理和统计
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("📁 文档管理")

    # 上传
    uploaded = st.file_uploader(
        "上传文档", type=["txt", "md", "pdf"],
        accept_multiple_files=True,
        help="支持 TXT, Markdown, PDF 格式",
    )
    if uploaded:
        import tempfile
        for file in uploaded:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(file.name).suffix
            ) as tmp:
                tmp.write(file.read())
                tmp_path = tmp.name
            try:
                n = agent.ingest_file(tmp_path)
                st.success(f"✅ {file.name}: {n} 个片段已索引")
            except Exception as exc:
                st.error(f"❌ {file.name}: {exc}")
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    st.divider()

    # 统计
    stats = agent.stats()
    st.metric("文档片段", stats["total_chunks"])
    st.metric("来源文件", stats["total_sources"])
    st.metric("词汇量", stats["vocab_size"])
    st.metric("短期记忆轮数", stats["short_term_turns"])
    st.metric("长期记忆事实", stats["long_term_facts"])

    st.divider()

    # 数据源列表
    sources = agent.vector_store.list_sources()
    if sources:
        st.subheader("📋 已索引文档")
        for s in sources:
            st.text(f"• {s}")

    st.divider()

    # 操作
    if st.button("🔄 清除对话"):
        agent.clear_conversation()
        st.session_state.messages = []
        st.rerun()

    if st.button("🗑️ 清除所有数据"):
        agent.vector_store.clear()
        agent.clear_conversation()
        st.session_state.messages = []
        st.rerun()

    # 检索数
    top_k = st.slider("检索片段数", 1, 15, 5)

    st.divider()
    st.caption(f"模型: {agent.model}")

# ---------------------------------------------------------------------------
# 聊天区域
# ---------------------------------------------------------------------------

# 显示历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "sources" in msg and msg["sources"]:
            with st.expander(f"📖 参考来源 ({len(msg['sources'])}个)"):
                for s in msg["sources"]:
                    st.caption(f"• {s}")

# 输入
if question := st.chat_input("输入问题..."):
    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(question)
    st.session_state.messages.append({"role": "user", "content": question})

    # RAG 查询
    with st.spinner("检索中..."):
        response = agent.query(question, top_k=top_k)

    # 显示回答
    with st.chat_message("assistant"):
        st.markdown(response.answer)
        if response.sources:
            with st.expander(f"📖 参考来源 ({len(response.sources)}个) · ⏱ {response.elapsed_ms:.0f}ms"):
                for s in response.sources:
                    st.caption(f"• {s}")

    msg_data = {
        "role": "assistant",
        "content": response.answer,
        "sources": response.sources,
    }
    st.session_state.messages.append(msg_data)
