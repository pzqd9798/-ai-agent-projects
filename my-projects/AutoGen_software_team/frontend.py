"""Streamlit 前端 — AutoGen 软件研发团队交互界面.

启动:
    # 先启动后端
    python backend.py

    # 再启动前端
    streamlit run frontend.py
"""

import sys
import json
import time
from pathlib import Path
import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

API = "http://localhost:8001"

# ---------------------------------------------------------------------------
# 页面配置
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="AutoGen 软件研发团队",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 AutoGen 软件研发团队")
st.caption("ProductManager → Engineer → CodeReviewer → UserProxy · 实时协作")

# ---------------------------------------------------------------------------
# 获取预设任务
# ---------------------------------------------------------------------------

@st.cache_data(ttl=30)
def get_presets() -> dict:
    try:
        r = requests.get(f"{API}/api/presets", timeout=3)
        return r.json().get("presets", {})
    except Exception:
        return {}

# ---------------------------------------------------------------------------
# 侧边栏 — 任务配置
# ---------------------------------------------------------------------------

with st.sidebar:
    st.subheader("📋 任务配置")

    presets = get_presets()
    preset_names = ["自定义任务"] + list(presets.keys())
    preset_choice = st.selectbox("选择预设任务", preset_names, index=0)

    if preset_choice != "自定义任务" and preset_choice in presets:
        st.info(presets[preset_choice])
        task_text = ""  # 使用预设
    else:
        task_text = st.text_area(
            "任务描述",
            placeholder="用自然语言描述你想要开发的软件...\n\n例如：开发一个天气预报查询系统，使用 Streamlit 做前端，调用公开 API 获取数据。",
            height=150,
        )

    max_turns = st.slider("最大对话轮次", 10, 50, 20)

    run_btn = st.button("🚀 启动团队", type="primary", use_container_width=True)

# ---------------------------------------------------------------------------
# 主区域
# ---------------------------------------------------------------------------

# 初始化 session
if "messages" not in st.session_state:
    st.session_state.messages = []
if "task_id" not in st.session_state:
    st.session_state.task_id = None
if "running" not in st.session_state:
    st.session_state.running = False

# 角色颜色映射
ROLE_COLORS = {
    "ProductManager": "#38bdf8",
    "Engineer": "#4ade80",
    "CodeReviewer": "#fbbf24",
    "UserProxy": "#c084fc",
    "system": "#94a3b8",
}
ROLE_ICONS = {
    "ProductManager": "📋",
    "Engineer": "💻",
    "CodeReviewer": "🔍",
    "UserProxy": "🧪",
    "system": "⚙️",
}

# ---------------------------------------------------------------------------
# 运行团队
# ---------------------------------------------------------------------------

if run_btn:
    task = task_text if preset_choice == "自定义任务" else ""
    preset = "" if preset_choice == "自定义任务" else preset_choice

    if not task and not preset:
        st.error("请输入任务描述或选择预设任务")
    else:
        try:
            resp = requests.post(f"{API}/api/run", json={
                "task": task,
                "preset": preset,
                "max_turns": max_turns,
            }, timeout=5)
            data = resp.json()
            st.session_state.task_id = data["task_id"]
            st.session_state.messages = []
            st.session_state.running = True
            st.rerun()
        except Exception as e:
            st.error(f"无法连接后端: {e}")
            st.info("请先启动后端: python backend.py")

# ---------------------------------------------------------------------------
# 消息展示
# ---------------------------------------------------------------------------

chat_container = st.container()

with chat_container:
    for msg in st.session_state.messages:
        role = msg["role"]
        color = ROLE_COLORS.get(role, "#94a3b8")
        icon = ROLE_ICONS.get(role, "💬")

        with st.chat_message(role, avatar=icon):
            if msg["type"] == "error":
                st.error(msg["content"])
            else:
                st.markdown(
                    f'<span style="color:{color};font-weight:600">[{role}]</span>',
                    unsafe_allow_html=True,
                )
                st.text(msg["content"][:3000])

# ---------------------------------------------------------------------------
# 实时刷新 (仅当任务运行时)
# ---------------------------------------------------------------------------

if st.session_state.running and st.session_state.task_id:
    # 从后端 SSE 拉取新消息
    try:
        resp = requests.get(
            f"{API}/api/stream/{st.session_state.task_id}",
            stream=True, timeout=120,
        )
        new_messages = []
        for line in resp.iter_lines():
            if line:
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data.get("type") == "timeout" or data.get("role") == "system":
                        if data.get("type") == "timeout":
                            st.warning("任务超时")
                        st.session_state.running = False
                        break
                    new_messages.append(data)

        if new_messages:
            st.session_state.messages = new_messages
            st.session_state.running = any(
                m["type"] != "error" for m in new_messages
            ) and len(new_messages) > 0

        # 检查是否完成
        status_resp = requests.get(
            f"{API}/api/status/{st.session_state.task_id}", timeout=3
        )
        status = status_resp.json()
        if status["status"] in ("done", "error"):
            st.session_state.running = False

    except Exception:
        pass

    # 自动刷新
    if st.session_state.running:
        time.sleep(1)
        st.rerun()

# ---------------------------------------------------------------------------
# 状态条
# ---------------------------------------------------------------------------

if st.session_state.task_id:
    try:
        sr = requests.get(
            f"{API}/api/status/{st.session_state.task_id}", timeout=3
        )
        s = sr.json()
        col1, col2, col3 = st.columns(3)
        col1.metric("状态", s["status"])
        col2.metric("消息数", s["message_count"])
        col3.metric("任务ID", st.session_state.task_id)
    except Exception:
        pass
