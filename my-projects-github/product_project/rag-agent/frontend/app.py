"""RAG Agent Pro — Streamlit 前端.

启动: streamlit run frontend/app.py

页面:
    - 🏠 首页 — 产品介绍
    - 📚 知识库 — 管理知识库 + 文档上传
    - 💬 对话 — RAG 问答
    - 🔍 检索 — 纯语义搜索
    - 🧠 记忆 — 用户偏好看板
"""

import sys
import os
import json
from pathlib import Path

# 确保项目根在 path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE = os.getenv("API_BASE", "http://localhost:8000")

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="RAG Agent Pro",
    page_icon="📚",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 侧边导航
# ---------------------------------------------------------------------------

st.sidebar.title("📚 RAG Agent Pro")
st.sidebar.caption("企业级检索增强生成平台")

page = st.sidebar.radio(
    "导航",
    ["🏠 首页", "📚 知识库", "💬 对话", "🔍 检索", "🧠 记忆"],
)

st.sidebar.divider()

# 认证状态
if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.user = None

if st.session_state.token:
    st.sidebar.success(f"👤 {st.session_state.user}")
    if st.sidebar.button("🚪 退出登录"):
        st.session_state.token = None
        st.session_state.user = None
        st.rerun()
else:
    with st.sidebar.expander("🔑 登录/注册"):
        auth_mode = st.radio("模式", ["登录", "注册"], horizontal=True, label_visibility="collapsed")
        username = st.text_input("用户名")
        password = st.text_input("密码", type="password")

        if st.button("确定", use_container_width=True):
            endpoint = "/api/auth/register" if auth_mode == "注册" else "/api/auth/login"
            try:
                resp = requests.post(
                    f"{API_BASE}{endpoint}",
                    json={"username": username, "password": password},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.user = data["username"]
                    st.rerun()
                else:
                    st.error(resp.json().get("detail", "请求失败"))
            except Exception as e:
                st.error(f"连接失败: {e}")

st.sidebar.divider()
st.sidebar.caption(f"API: {API_BASE}")

# ---------------------------------------------------------------------------
# 请求工具
# ---------------------------------------------------------------------------

def api_headers() -> dict:
    h = {}
    if st.session_state.token:
        h["Authorization"] = f"Bearer {st.session_state.token}"
    return h


# ---------------------------------------------------------------------------
# 🏠 首页
# ---------------------------------------------------------------------------

if page == "🏠 首页":
    col1, col2 = st.columns([2, 1])

    with col1:
        st.title("📚 RAG Agent Pro")
        st.subheader("企业级检索增强生成知识助手平台")

        st.markdown("""
        ### 核心能力

        | 能力 | 说明 |
        |------|------|
        | 📄 **多格式摄取** | PDF, Markdown, TXT → 自动分块索引 |
        | 🔍 **混合检索** | BM25 关键词 + 向量语义 + 重排序 |
        | 🤖 **增强生成** | 检索 → 上下文组装 → LLM 生成 |
        | 📚 **多知识库** | 隔离管理、标签分类、全生命周期 |
        | 🧠 **双记忆** | 短期对话流 + 长期用户偏好 |
        | 🌊 **流式输出** | SSE 实时推送生成 token |
        | 🔐 **多租户** | JWT + API Key 双认证 |
        """)

    with col2:
        st.markdown("### 系统状态")
        try:
            resp = requests.get(f"{API_BASE}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"✅ {data.get('status', 'ok')}")
                st.metric("版本", data.get("version", "-"))
                st.metric("嵌入器", data.get("embedder", "-"))
                st.metric("模型", data.get("model", "-"))
            else:
                st.error("服务异常")
        except Exception:
            st.error("无法连接后端")

        st.markdown("### 快速开始")
        st.markdown("""
        1. 注册/登录
        2. 创建知识库
        3. 上传文档
        4. 开始对话
        """)

# ---------------------------------------------------------------------------
# 📚 知识库
# ---------------------------------------------------------------------------

elif page == "📚 知识库":
    st.title("📚 知识库管理")

    if not st.session_state.token:
        st.warning("请先登录")
        st.stop()

    # 创建知识库
    with st.expander("➕ 创建知识库"):
        name = st.text_input("名称")
        desc = st.text_area("描述")
        tags = st.text_input("标签 (逗号分隔)")
        if st.button("创建", use_container_width=True):
            resp = requests.post(
                f"{API_BASE}/api/knowledge",
                json={
                    "name": name,
                    "description": desc,
                    "tags": [t.strip() for t in tags.split(",") if t.strip()],
                },
                headers=api_headers(),
            )
            if resp.status_code == 200:
                st.success("知识库已创建")
                st.rerun()
            else:
                st.error(resp.json().get("detail", "创建失败"))

    # 列表
    try:
        resp = requests.get(f"{API_BASE}/api/knowledge", headers=api_headers())
        if resp.status_code == 200:
            kbs = resp.json()
            if not kbs:
                st.info("还没有知识库，创建一个吧")
            else:
                for kb in kbs:
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                        with c1:
                            st.subheader(kb["name"])
                            st.caption(kb["description"] or "无描述")
                            if kb["tags"]:
                                tags_str = " · ".join(kb["tags"])
                                st.caption(f"🏷 {tags_str}")
                        with c2:
                            st.metric("文档", kb["document_count"])
                        with c3:
                            st.metric("片段", kb["chunk_count"])
                        with c4:
                            # 上传按钮
                            with st.popover("📤 上传"):
                                uploaded = st.file_uploader(
                                    f"上传到 {kb['name']}",
                                    type=["txt", "md", "pdf"],
                                    key=f"upload_{kb['id']}",
                                )
                                if uploaded:
                                    files = {"file": (uploaded.name, uploaded.read(), uploaded.type)}
                                    resp_up = requests.post(
                                        f"{API_BASE}/api/documents/upload",
                                        files=files,
                                        data={"kb_id": kb["id"]},
                                        headers=api_headers(),
                                    )
                                    if resp_up.status_code == 200:
                                        st.success(resp_up.json().get("message", "OK"))
                                        st.rerun()
                                    else:
                                        st.error(resp_up.json().get("detail", "上传失败"))
    except Exception as e:
        st.error(f"连接 API 失败: {e}")

# ---------------------------------------------------------------------------
# 💬 对话
# ---------------------------------------------------------------------------

elif page == "💬 对话":
    st.title("💬 RAG 对话")

    if not st.session_state.token:
        st.warning("请先登录")
        st.stop()

    # 选择知识库
    resp = requests.get(f"{API_BASE}/api/knowledge", headers=api_headers())
    kbs = resp.json() if resp.status_code == 200 else []
    kb_options = {kb["name"]: kb["id"] for kb in kbs}

    if not kb_options:
        st.warning("请先创建知识库并上传文档")
        st.stop()

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_kb = st.selectbox("选择知识库", list(kb_options.keys()))
    with col2:
        top_k = st.slider("检索片段数", 1, 15, 5)

    kb_id = kb_options[selected_kb]

    # 初始化聊天
    if "rag_messages" not in st.session_state:
        st.session_state.rag_messages = []
        st.session_state.session_id = None

    # 显示历史
    for msg in st.session_state.rag_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sources"):
                with st.expander(f"📖 参考来源 ({len(msg['sources'])}个)"):
                    for s in msg["sources"]:
                        st.caption(f"• {s.get('filename', '?')}#{s.get('chunk_index', '?')} (相关度: {s.get('score', '?')})")

    # 输入
    if question := st.chat_input("输入问题..."):
        with st.chat_message("user"):
            st.markdown(question)
        st.session_state.rag_messages.append({"role": "user", "content": question})

        with st.chat_message("assistant"):
            with st.spinner("检索中..."):
                resp = requests.post(
                    f"{API_BASE}/api/chat",
                    json={
                        "question": question,
                        "kb_id": kb_id,
                        "session_id": st.session_state.session_id,
                        "top_k": top_k,
                    },
                    headers=api_headers(),
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.markdown(data["answer"])
                    if data["sources"]:
                        with st.expander(f"📖 参考来源 ({len(data['sources'])}个) · ⏱ {data['elapsed_ms']:.0f}ms"):
                            for s in data["sources"]:
                                st.caption(
                                    f"• {s.get('filename', '?')}#{s.get('chunk_index', '?')} "
                                    f"(相关度: {s.get('score', '?')})"
                                )
                                if s.get("snippet"):
                                    st.text(s["snippet"][:200])

                    st.session_state.rag_messages.append({
                        "role": "assistant",
                        "content": data["answer"],
                        "sources": data["sources"],
                    })
                    st.session_state.session_id = data["session_id"]
                else:
                    st.error(resp.json().get("detail", "请求失败"))

    # 清除对话
    if st.button("🔄 清除对话"):
        st.session_state.rag_messages = []
        st.session_state.session_id = None
        st.rerun()

# ---------------------------------------------------------------------------
# 🔍 检索
# ---------------------------------------------------------------------------

elif page == "🔍 检索":
    st.title("🔍 语义检索")

    if not st.session_state.token:
        st.warning("请先登录")
        st.stop()

    resp = requests.get(f"{API_BASE}/api/knowledge", headers=api_headers())
    kbs = resp.json() if resp.status_code == 200 else []
    kb_options = {kb["name"]: kb["id"] for kb in kbs}

    if not kb_options:
        st.warning("请先创建知识库并上传文档")
        st.stop()

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_kb = st.selectbox("选择知识库", list(kb_options.keys()), key="search_kb")
    with col2:
        top_k = st.slider("返回结果数", 1, 30, 10, key="search_topk")

    query = st.text_input("搜索关键词或问题")
    if st.button("🔍 搜索") and query:
        with st.spinner("检索中..."):
            resp = requests.post(
                f"{API_BASE}/api/documents/search",
                json={
                    "query": query,
                    "kb_id": kb_options[selected_kb],
                    "top_k": top_k,
                },
                headers=api_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                st.success(f"找到 {data['total']} 个相关片段 · ⏱ {data['elapsed_ms']:.0f}ms")

                for i, r in enumerate(data["results"]):
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**#{i+1}** · {r['source']}")
                            st.text(r["text"][:500])
                        with c2:
                            st.metric("相关度", f"{r['score']:.4f}")
            else:
                st.error(resp.json().get("detail", "搜索失败"))

# ---------------------------------------------------------------------------
# 🧠 记忆
# ---------------------------------------------------------------------------

elif page == "🧠 记忆":
    st.title("🧠 用户记忆")

    if not st.session_state.token:
        st.warning("请先登录")
        st.stop()

    # 获取用户信息和记忆
    try:
        resp = requests.get(f"{API_BASE}/api/auth/me", headers=api_headers())
        if resp.status_code == 200:
            user = resp.json()
            st.subheader(f"👤 {user['username']}")
            st.json({
                "role": user["role"],
                "api_key": user.get("api_key", "N/A")[:20] + "..." if user.get("api_key") else "N/A",
                "created_at": user.get("created_at", "-"),
            })
    except Exception:
        st.warning("无法获取用户信息")

    st.divider()
    st.caption("长期记忆由系统自动从对话中提取。偏好和事实会在后续对话中自动引用。")
