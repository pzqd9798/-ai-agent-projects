"""Streamlit Web UI — Agent 聊天界面.

启动方式: streamlit run app/ui/streamlit_app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
from app.engine.agent_loop import Agent
from app.security.guard import scan_input, sanitize_output
from app.intelligence.soul import assemble_system_prompt

st.set_page_config(page_title="Agent Platform", page_icon="🤖", layout="wide")

st.title("🤖 Agent Platform")
st.caption("生产级 AI Agent — 多通道 · 工具调度 · 记忆 · 安全")

# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------

if "agent" not in st.session_state:
    system_prompt = assemble_system_prompt()
    st.session_state.agent = Agent(system_prompt=system_prompt)
    st.session_state.agent.load_or_create_session()
    st.session_state.messages = []
    st.session_state.context_pct = 0.0

agent: Agent = st.session_state.agent

# ---------------------------------------------------------------------------
# 侧边栏 — 会话管理
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("📋 会话")
    sessions = agent.session_store.list_sessions()
    for sid, meta in sessions[:20]:
        active = " ← 当前" if sid == agent.session_store.current_session_id else ""
        label = meta.get("label", "")
        msg_count = meta.get("message_count", 0)
        st.text(f"{sid}{f' ({label})' if label else ''} [{msg_count}条]{active}")

    st.divider()

    # 上下文使用
    estimated, max_t, pct = agent.get_context_usage()
    st.metric("上下文使用", f"{pct:.1f}%", f"~{estimated:,} / {max_t:,} tokens")

    if st.button("🗜️ 压缩历史"):
        reduced = agent.compact_now()
        st.success(f"减 {abs(reduced)} 条消息")

    if st.button("🆕 新建会话"):
        sid = agent.session_store.create_session("web")
        agent.messages = []
        st.session_state.messages = []
        st.rerun()

    st.divider()

    # 手动开启 browser-use 工具
    use_browser = st.toggle("🌐 启用浏览器工具", value=False,
                            help="需要安装 browser-use[core]")
    if use_browser:
        try:
            import app.tools.browser_tool  # noqa: F401
            st.success("浏览器工具已启用")
        except ImportError:
            st.error("browser-use 未安装: pip install 'browser-use[core]'")

# ---------------------------------------------------------------------------
# 聊天界面
# ---------------------------------------------------------------------------

# 安全状态指示器
scan_status = st.empty()

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入
if user_msg := st.chat_input("输入消息..."):
    # 安全检查
    scan = scan_input(user_msg)
    if not scan["safe"]:
        st.error(f"⚠️ 输入被安全护栏拦截: {'; '.join(scan['reasons'])}")
        st.stop()

    # 显示用户消息
    with st.chat_message("user"):
        st.markdown(user_msg)
    st.session_state.messages.append({"role": "user", "content": user_msg})

    # 调用 Agent
    with st.spinner("思考中..."):
        reply = agent.run_turn(user_msg)

    # 输出脱敏
    reply, replaced = sanitize_output(reply)

    # 显示回复
    with st.chat_message("assistant"):
        st.markdown(reply)
    st.session_state.messages.append({"role": "assistant", "content": reply})

    # 脱敏提示
    if replaced:
        st.info(f"🔒 已脱敏: {', '.join(set(replaced))}")

    # 更新上下文
    _, _, pct = agent.get_context_usage()
    st.session_state.context_pct = pct
