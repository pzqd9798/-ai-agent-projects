"""Coding Agent — 产品级软件研发助手.

启动: streamlit run frontend.py

三阶段流程：
  Phase 1: 产品经理分析需求 → 用户审核
  Phase 2: 工程师编写代码 → 代码预览 → 用户审核
  Phase 3: 审查员检查代码 → 用户最终确认
"""

import sys
import asyncio
import re
import os
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

from team.orchestrator import PRESET_TASKS, create_model_client
from team.agents import (
    create_product_manager,
    create_engineer,
    create_code_reviewer,
)
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.messages import TextMessage

ROLE_COLORS = {
    "ProductManager": "#38bdf8",
    "Engineer": "#4ade80",
    "CodeReviewer": "#fbbf24",
    "User": "#c084fc",
}

# ---------------------------------------------------------------------------
# Agent 调用
# ---------------------------------------------------------------------------

async def call_agent(agent: AssistantAgent, prompt: str) -> str:
    """调用单个 Agent 并收集其回复."""
    response = await agent.on_messages(
        [TextMessage(content=prompt, source="User")],
        cancellation_token=None,
    )
    return response.chat_message.content if hasattr(response.chat_message, "content") else str(response.chat_message)


def run_phase(agent: AssistantAgent, prompt: str) -> str:
    """同步包装器：在线程中运行异步 agent 调用."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(call_agent(agent, prompt))
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Session 状态
# ---------------------------------------------------------------------------

DEFAULTS = {
    "page": "home",
    "phase": "plan",
    "plan_text": "",
    "code_text": "",
    "review_text": "",
    "feedback": "",
    "history": [],
    "task": "",
    "preview_proc": None,
    "preview_port": 8502,
}

for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def extract_code(text: str) -> list[dict]:
    """从文本中提取代码块."""
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": m[0] or "text", "code": m[1].strip()} for m in matches]


def save_preview_code(code_text: str) -> Path:
    """提取代码保存为临时预览文件."""
    blocks = extract_code(code_text)
    if not blocks:
        return None
    merged = "\n\n".join(b["code"] for b in blocks)
    preview_dir = Path(__file__).resolve().parent / "output" / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    filepath = preview_dir / "preview_app.py"
    filepath.write_text(merged, encoding="utf-8")
    return filepath


def start_preview():
    """启动 Streamlit 预览子进程."""
    import subprocess
    import time
    filepath = save_preview_code(st.session_state.code_text)
    if not filepath:
        return None

    # 杀掉旧进程
    if st.session_state.preview_proc:
        try:
            st.session_state.preview_proc.kill()
            st.session_state.preview_proc.wait(timeout=3)
        except Exception:
            pass

    port = 8502
    proc = subprocess.Popen(
        ["streamlit", "run", str(filepath), "--server.port", str(port),
         "--server.headless", "true", "--browser.gatherUsageStats", "false"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(3)  # 等 Streamlit 启动
    st.session_state.preview_proc = proc
    st.session_state.preview_port = port
    return port


def build_prompt(phase: str) -> str:
    """基于历史上下文构建当前阶段的 prompt."""
    feedback = st.session_state.feedback
    task = st.session_state.task
    plan = st.session_state.plan_text
    code = st.session_state.code_text

    if phase == "plan":
        return f"请分析以下开发任务的需求：\n\n{task}"

    elif phase == "code":
        prompt = f"## 产品需求分析\n{plan}\n\n## 开发任务\n{task}"
        if feedback:
            prompt += f"\n\n## 用户反馈\n{feedback}\n请根据反馈调整代码。"
        prompt += "\n\n请编写完整的可运行代码。代码用 ```python 和 ``` 包裹。"
        return prompt

    elif phase == "review":
        prompt = f"## 任务\n{task}\n\n## 需求分析\n{plan}\n\n## 代码\n{code}"
        if feedback:
            prompt += f"\n\n## 用户反馈\n{feedback}\n请针对反馈重新审查。"
        prompt += "\n\n请审查代码质量、安全性和最佳实践，给出具体的改进建议。"
        return prompt

    return task


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Coding Agent", page_icon="🤖", layout="wide")

# ========================
# 首页
# ========================
if st.session_state.page == "home":

    st.markdown("""
    <style>
    .home-title { font-size: 36px; font-weight: 700; margin-bottom: 4px; }
    .home-sub { color: #94a3b8; margin-bottom: 24px; }
    .hero-card { background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border: 1px solid #334155; border-radius: 16px; padding: 28px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<p class="home-title">🤖 Coding Agent</p>', unsafe_allow_html=True)
    st.markdown('<p class="home-sub">AI 软件研发助手 · 需求分析 → 代码生成 → 质量审查</p>',
                unsafe_allow_html=True)

    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("### 📋 开发任务")

        preset = st.selectbox(
            "预设任务",
            ["自定义任务"] + list(PRESET_TASKS.keys()),
            index=1,
            label_visibility="collapsed",
        )

        default_text = PRESET_TASKS.get(preset, "")
        task_input = st.text_area(
            "任务描述",
            value=default_text if preset != "自定义任务" else "",
            height=220,
            placeholder="用自然语言描述你要开发的软件...",
            key="task_input",
        )

        c1, c2 = st.columns([1, 1])
        with c1:
            if st.button("🚀 启动", type="primary", use_container_width=True):
                st.session_state.task = task_input.strip()
                st.session_state.page = "workspace"
                st.session_state.phase = "plan"
                st.session_state.plan_text = ""
                st.session_state.code_text = ""
                st.session_state.review_text = ""
                st.session_state.feedback = ""
                st.session_state.history = []

                # Phase 1: 直接执行 PM 分析
                with st.spinner("📋 产品经理正在分析需求..."):
                    model_client = create_model_client()
                    pm = create_product_manager(model_client)
                    plan = run_phase(pm, build_prompt("plan"))
                    st.session_state.plan_text = plan
                    st.session_state.history.append({"phase": "plan", "role": "ProductManager", "content": plan})

                st.rerun()

    with col2:
        st.markdown("### 👥 工作流程")
        phases = [
            ("📋", "需求分析", "产品经理分析需求，拆解功能模块，给出技术方案"),
            ("💻", "代码生成", "工程师根据需求编写完整代码，支持反馈迭代"),
            ("🔍", "质量审查", "审查员检查代码质量、安全性和最佳实践"),
            ("✅", "交付确认", "用户审核通过，保存项目记录"),
        ]
        for icon, title, desc in phases:
            st.markdown(
                f'<div class="hero-card">'
                f'<span style="font-size:24px">{icon}</span> '
                f'<span style="font-size:16px;font-weight:600">{title}</span>'
                f'<br><small style="color:#94a3b8">{desc}</small></div>',
                unsafe_allow_html=True,
            )

# ========================
# 工作区
# ========================
else:

    # ── 顶部状态条 ──
    phase_labels = {
        "plan": ("📋 需求分析", "ProductManager 正在分析"),
        "code": ("💻 代码生成", "Engineer 正在编码"),
        "review": ("🔍 质量审查", "CodeReviewer 正在检查"),
        "done": ("✅ 完成", "所有阶段已完成"),
    }

    cur_label, cur_desc = phase_labels.get(st.session_state.phase, phase_labels["plan"])

    with st.container():
        st.markdown(f"### {cur_label}")
        st.caption(cur_desc)

        # 进度条
        phases_done = {"plan": 1, "code": 2, "review": 3, "done": 4}
        current_step = phases_done.get(st.session_state.phase, 1)
        st.progress(current_step / 4, text=f"阶段 {current_step} / 4")

        if st.button("🏠 回到首页"):
            st.session_state.page = "home"
            st.rerun()

    st.markdown("---")

    # ── 左右分栏 ──
    left, right = st.columns([3, 2])

    # ============ 左侧：对话区 ============
    with left:
        for entry in st.session_state.history:
            role = entry["role"]
            phase = entry["phase"]
            color = ROLE_COLORS.get(role, "#94a3b8")
            content = entry["content"]

            if role == "User":
                with st.chat_message("user"):
                    st.markdown(content)
            else:
                with st.expander(f"{role} · {phase_labels.get(phase, ('',''))[0]}", expanded=(role != "User")):
                    st.markdown(content[:5000])

    # ============ 右侧：实时预览 + 操作 ============
    with right:
        # 实时预览
        if st.session_state.code_text and st.session_state.phase in ("code", "review", "done"):
            st.markdown("### 🖥️ 实时预览")

            if st.button("🚀 启动预览", use_container_width=True,
                         help="将生成的代码作为独立 App 启动并在下方展示"):
                port = start_preview()
                if port:
                    st.success(f"预览已启动 :{port}")
                    st.rerun()
                else:
                    st.warning("未检测到可执行代码")

            is_preview_running = (
                st.session_state.preview_proc is not None
                and st.session_state.preview_proc.poll() is None
            )

            if is_preview_running:
                st.caption(f"运行中 → http://localhost:{st.session_state.preview_port}")
                st.components.v1.iframe(
                    f"http://localhost:{st.session_state.preview_port}",
                    height=500, scrolling=True,
                )

        # 审查结果
        if st.session_state.review_text:
            with st.expander("🔍 审查报告", expanded=True):
                st.markdown(st.session_state.review_text[:3000])

        st.markdown("---")

        # 操作按钮
        phase = st.session_state.phase

        if phase == "plan":
            st.markdown("### ✋ 需求确认")
            feedback = st.text_area("反馈意见（可选）", height=80,
                                    placeholder="对需求分析有什么补充或修改意见？",
                                    key="plan_feedback")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ 确认，开始编码", use_container_width=True, type="primary"):
                    if feedback.strip():
                        st.session_state.feedback = feedback
                        st.session_state.history.append({"phase": "plan", "role": "User", "content": f"反馈: {feedback}"})
                    else:
                        st.session_state.feedback = ""

                    st.session_state.phase = "code"
                    with st.spinner("💻 工程师正在编写代码..."):
                        model_client = create_model_client()
                        eng = create_engineer(model_client)
                        code = run_phase(eng, build_prompt("code"))
                        st.session_state.code_text = code
                        st.session_state.history.append({"phase": "code", "role": "Engineer", "content": code})
                    st.rerun()

            with col_b:
                if st.button("🔄 重新分析", use_container_width=True):
                    new_task = st.session_state.task
                    if feedback.strip():
                        new_task = f"{new_task}\n\n用户补充需求: {feedback}"
                        st.session_state.task = new_task
                        st.session_state.feedback = feedback
                    st.session_state.history.append({"phase": "plan", "role": "User", "content": f"修改意见: {feedback or '重新分析'}"})

                    with st.spinner("📋 正在重新分析..."):
                        model_client = create_model_client()
                        pm = create_product_manager(model_client)
                        plan = run_phase(pm, build_prompt("plan"))
                        st.session_state.plan_text = plan
                        st.session_state.history.append({"phase": "plan", "role": "ProductManager", "content": plan})
                    st.rerun()

        elif phase == "code":
            st.markdown("### ✋ 代码审核")
            feedback = st.text_area("反馈意见（可选）", height=80,
                                    placeholder="对代码有什么修改意见？",
                                    key="code_feedback")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ 确认，开始审查", use_container_width=True, type="primary"):
                    if feedback.strip():
                        st.session_state.feedback = feedback
                        st.session_state.history.append({"phase": "code", "role": "User", "content": f"反馈: {feedback}"})
                    else:
                        st.session_state.feedback = ""

                    st.session_state.phase = "review"
                    with st.spinner("🔍 审查员正在检查代码..."):
                        model_client = create_model_client()
                        cr = create_code_reviewer(model_client)
                        review = run_phase(cr, build_prompt("review"))
                        st.session_state.review_text = review
                        st.session_state.history.append({"phase": "review", "role": "CodeReviewer", "content": review})
                    st.rerun()

            with col_b:
                if st.button("🔄 修改代码", use_container_width=True):
                    if feedback.strip():
                        st.session_state.feedback = feedback
                        st.session_state.history.append({"phase": "code", "role": "User", "content": f"修改意见: {feedback}"})
                    else:
                        st.session_state.feedback = "请重新生成代码"

                    with st.spinner("💻 工程师正在修改代码..."):
                        model_client = create_model_client()
                        eng = create_engineer(model_client)
                        code = run_phase(eng, build_prompt("code"))
                        st.session_state.code_text = code
                        st.session_state.history.append({"phase": "code", "role": "Engineer", "content": code})
                    st.rerun()

        elif phase == "review":
            st.markdown("### ✋ 最终确认")
            feedback = st.text_area("反馈意见（可选）", height=80,
                                    placeholder="还有什么需要调整的？",
                                    key="review_feedback")

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✅ 确认交付", use_container_width=True, type="primary"):
                    st.session_state.history.append({"phase": "done", "role": "User", "content": "✅ 确认交付"})
                    st.session_state.phase = "done"
                    st.rerun()

            with col_b:
                if st.button("🔄 重新审查/修改", use_container_width=True):
                    if feedback.strip():
                        st.session_state.feedback = feedback
                        st.session_state.history.append({"phase": "review", "role": "User", "content": f"修改意见: {feedback}"})
                    else:
                        st.session_state.feedback = "请重新审查并给出修改建议"

                    with st.spinner("🔍 正在重新审查..."):
                        model_client = create_model_client()
                        cr = create_code_reviewer(model_client)
                        review = run_phase(cr, build_prompt("review"))
                        st.session_state.review_text = review
                        st.session_state.history.append({"phase": "review", "role": "CodeReviewer", "content": review})

                        eng = create_engineer(model_client)
                        code = run_phase(eng, build_prompt("code"))
                        st.session_state.code_text = code
                        st.session_state.history.append({"phase": "code", "role": "Engineer", "content": code})
                    st.rerun()

        elif phase == "done":
            st.success("🎉 项目交付完成！")

            # 保存
            if st.button("💾 保存项目记录"):
                output_dir = Path(__file__).resolve().parent / "output"
                output_dir.mkdir(exist_ok=True)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                filepath = output_dir / f"project_{ts}.md"
                lines = [f"# Coding Agent 项目记录\n",
                         f"**任务**: {st.session_state.task}\n\n---\n"]
                for e in st.session_state.history:
                    lines.append(f"## {e['role']}\n\n{e['content']}\n\n---\n")
                filepath.write_text("\n".join(lines), encoding="utf-8")
                st.info(f"已保存: {filepath}")

            if st.button("🆕 开始新项目"):
                for k, v in DEFAULTS.items():
                    st.session_state[k] = v
                st.rerun()
