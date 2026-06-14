"""Coding Agent — 生产级 Streamlit 前端.

启动: streamlit run frontend/app.py

与后端 FastAPI 通过 HTTP 通信, 支持:
    - 用户注册/登录
    - 项目 CRUD
    - 三阶段流程驱动
    - Agent 模板选择
    - WebSocket 实时流式输出
    - 版本历史浏览
"""

import streamlit as st
import requests
import json
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

API_BASE = "http://localhost:8000"
WS_BASE = "ws://localhost:8000"

st.set_page_config(page_title="Coding Agent Pro", page_icon="🤖", layout="wide")

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
.main-header { font-size:32px; font-weight:700; color:#38bdf8; margin-bottom:4px; }
.sub-header { color:#94a3b8; margin-bottom:24px; font-size:16px; }
.stage-card { background:#1e293b; border:1px solid #334155; border-radius:12px;
              padding:20px; margin-bottom:12px; }
.role-tag { display:inline-block; padding:2px 10px; border-radius:12px;
            font-size:12px; font-weight:600; margin-right:8px; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session 初始化
# ---------------------------------------------------------------------------

KEYS = {
    "token": None, "user": None, "page": "login",
    "projects": [], "current_project": None,
    "phases": {}, "artifacts": [], "versions": [],
    "preview_url": None,
}

for k, v in KEYS.items():
    if k not in st.session_state:
        st.session_state[k] = v


def api_headers():
    """构造认证请求头."""
    h = {"Content-Type": "application/json"}
    if st.session_state.token:
        h["Authorization"] = f"Bearer {st.session_state.token}"
    return h


def api_post(path: str, data: dict) -> dict:
    """POST 请求."""
    try:
        r = requests.post(f"{API_BASE}{path}", json=data, headers=api_headers(), timeout=60)
        if r.status_code >= 400:
            st.error(f"API 错误 [{r.status_code}]: {r.text[:200]}")
            return None
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接到后端服务 (http://localhost:8000)")
        return None
    except Exception as e:
        st.error(f"请求失败: {str(e)}")
        return None


def api_get(path: str) -> dict | list | None:
    """GET 请求."""
    try:
        r = requests.get(f"{API_BASE}{path}", headers=api_headers(), timeout=15)
        if r.status_code >= 400:
            st.error(f"API 错误 [{r.status_code}]: {r.text[:200]}")
            return None
        return r.json()
    except requests.exceptions.ConnectionError:
        st.error("无法连接到后端服务")
        return None


# ========================================================================
# 登录页
# ========================================================================

def page_login():
    st.markdown('<p class="main-header">🤖 Coding Agent Pro</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">基于 AutoGen 多 Agent 协作的生产级软件研发平台</p>',
                unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["登录", "注册"])

    with tab1:
        username = st.text_input("用户名", key="login_username")
        password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录", type="primary", use_container_width=True):
            r = requests.post(f"{API_BASE}/api/auth/login",
                            json={"username": username, "password": password})
            if r.status_code == 200:
                data = r.json()
                st.session_state.token = data["access_token"]
                st.session_state.user = data["user"]
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error(r.json().get("detail", "登录失败"))

    with tab2:
        new_user = st.text_input("用户名", key="reg_username")
        new_pw = st.text_input("密码", type="password", key="reg_password")
        if st.button("注册", type="primary", use_container_width=True):
            r = requests.post(f"{API_BASE}/api/auth/register",
                            json={"username": new_user, "password": new_pw})
            if r.status_code == 200:
                data = r.json()
                st.session_state.token = data["access_token"]
                st.session_state.user = data["user"]
                st.session_state.page = "dashboard"
                st.rerun()
            else:
                st.error(r.json().get("detail", "注册失败"))


# ========================================================================
# 项目面板
# ========================================================================

def page_dashboard():
    user = st.session_state.user
    st.markdown(f'<p class="main-header">👋 你好, {user["username"]}</p>',
                unsafe_allow_html=True)
    st.caption("管理你的软件研发项目")

    # 侧边栏
    with st.sidebar:
        st.title("🤖 Coding Agent Pro")
        st.caption(f"用户: {user['username']} ({user['role']})")

        st.markdown("---")
        if st.button("📋 项目管理", use_container_width=True):
            st.session_state.page = "dashboard"
            st.session_state.current_project = None
            st.rerun()
        if st.button("🆕 新建项目", use_container_width=True, type="primary"):
            st.session_state.page = "new_project"
            st.rerun()
        if st.button("📦 Agent 模板", use_container_width=True):
            st.session_state.page = "templates"
            st.rerun()
        st.markdown("---")
        if st.button("🚪 退出登录", use_container_width=True):
            for k in KEYS:
                st.session_state[k] = KEYS[k]
            st.rerun()

    # 主区域: 项目列表
    projects = api_get("/api/projects")
    if projects is None:
        st.warning("加载项目列表失败, 请确保后端已启动")
        return

    st.session_state.projects = projects

    if not projects:
        st.info("还没有项目, 点击左侧「新建项目」开始")
        return

    for proj in projects:
        status_colors = {
            "draft": "#64748b", "planning": "#38bdf8",
            "coding": "#4ade80", "done": "#f59e0b",
        }
        color = status_colors.get(proj["status"], "#64748b")

        with st.container():
            st.markdown(f"""
            <div class="stage-card">
              <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                  <span style="font-size:18px; font-weight:600;">{proj['name']}</span>
                  <span style="margin-left:12px; color:{color}; font-size:13px;">● {proj['status']}</span>
                </div>
                <span style="color:#64748b; font-size:13px;">{proj['updated_at'][:19]}</span>
              </div>
              <p style="color:#94a3b8; margin-top:8px; font-size:14px;">{proj['description'][:120]}</p>
              <span style="color:#64748b; font-size:12px;">{proj['phase_count']} 个阶段 · 模板: {proj.get('template_id', 'full-stack')}</span>
            </div>
            """, unsafe_allow_html=True)

            col_a, col_b, col_c = st.columns([1, 1, 1])
            with col_a:
                if st.button(f"📋 打开", key=f"open_{proj['id']}"):
                    st.session_state.current_project = proj
                    st.session_state.page = "workspace"
                    st.rerun()
            with col_b:
                if st.button(f"📦 版本", key=f"ver_{proj['id']}"):
                    st.session_state.current_project = proj
                    st.session_state.page = "versions"
                    st.rerun()
            with col_c:
                if st.button(f"🗑️ 删除", key=f"del_{proj['id']}"):
                    r = requests.delete(f"{API_BASE}/api/projects/{proj['id']}",
                                       headers=api_headers())
                    if r.status_code == 200:
                        st.success("已删除")
                        st.rerun()


# ========================================================================
# 新建项目
# ========================================================================

def page_new_project():
    st.markdown("### 🆕 新建项目")

    name = st.text_input("项目名称", placeholder="例如: BTC 价格追踪器")
    description = st.text_area("需求描述", height=200,
                               placeholder="用自然语言描述你要开发的软件...")

    # 模板选择
    st.markdown("#### 选择 Agent 团队模板")
    templates = {
        "full-stack": ("全栈 Web 应用", "4人团队: PM + 工程师 + 审查员 + 用户代理"),
        "cli-tool": ("命令行工具", "3人团队: PM + 工程师 + 审查员"),
        "api-service": ("API 后端服务", "3人团队: PM + 后端工程师 + 审查员"),
    }
    template_id = st.selectbox(
        "团队模板",
        list(templates.keys()),
        format_func=lambda x: f"{templates[x][0]} — {templates[x][1]}",
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 创建项目", type="primary", use_container_width=True):
            if not name or not description:
                st.error("请填写项目名称和需求描述")
            else:
                result = api_post("/api/projects", {
                    "name": name,
                    "description": description,
                    "template_id": template_id,
                })
                if result:
                    st.success("项目已创建")
                    st.session_state.current_project = result
                    st.session_state.page = "workspace"
                    st.rerun()
    with col2:
        if st.button("↩ 返回", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()


# ========================================================================
# 工作区 (核心)
# ========================================================================

def page_workspace():
    proj = st.session_state.current_project
    if not proj:
        st.session_state.page = "dashboard"
        st.rerun()
        return

    # 顶部导航
    st.markdown(f"### 🤖 {proj['name']}")
    st.caption(f"状态: {proj['status']} · 模板: {proj.get('template_id', 'full-stack')}")

    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        if st.button("↩ 返回列表", use_container_width=True):
            st.session_state.page = "dashboard"
            st.session_state.current_project = None
            st.rerun()

    st.markdown("---")

    # 加载阶段数据
    phases = api_get(f"/api/projects/{proj['id']}/phases") or []
    artifacts = api_get(f"/api/projects/{proj['id']}/artifacts") or []
    st.session_state.phases = {p["phase"]: p for p in phases}
    st.session_state.artifacts = artifacts

    # 三阶段进度
    phase_config = {
        "plan": ("📋 需求分析", "ProductManager"),
        "code": ("💻 代码生成", "Engineer"),
        "review": ("🔍 质量审查", "CodeReviewer"),
    }

    current_phase_done = {
        p: st.session_state.phases.get(p, {}).get("status") == "done"
        for p in ["plan", "code", "review"]
    }

    # 进度条
    progress_value = sum(1 for v in current_phase_done.values() if v) / 3
    st.progress(progress_value, text=f"进度: {int(progress_value * 100)}%")

    # 阶段卡片
    for phase, (icon_label, role) in phase_config.items():
        is_done = current_phase_done[phase]
        prev_done = True  # plan 总是可以执行

        if phase == "code":
            prev_done = current_phase_done["plan"]
        elif phase == "review":
            prev_done = current_phase_done["code"]

        with st.container():
            bg = "#0f172a" if is_done else "#1e293b"
            border = "#4ade80" if is_done else "#334155"
            st.markdown(f"""
            <div style="background:{bg}; border:2px solid {border}; border-radius:12px;
                        padding:20px; margin-bottom:16px;">
              <span style="font-size:20px;">{icon_label}</span>
              <span class="role-tag" style="background:#38bdf8; color:#0f172a;">{role}</span>
              {'✅ 已完成' if is_done else '⏳ 待执行'}
            </div>
            """, unsafe_allow_html=True)

            if not is_done and prev_done:
                feedback = st.text_area(
                    "补充反馈 (可选)", key=f"fb_{phase}",
                    placeholder="对该阶段有什么补充要求？",
                )

                col_exec, col_skip = st.columns([2, 1])
                with col_exec:
                    if st.button(f"▶ 执行 {icon_label}", key=f"exec_{phase}",
                                type="primary"):
                        with st.spinner(f"{icon_label} {role} 工作中..."):
                            result = api_post(
                                f"/api/projects/{proj['id']}/phases/{phase}",
                                {"phase": phase, "feedback": feedback or None}
                            )
                            if result:
                                st.success(f"{icon_label} 完成")
                                st.rerun()

            # 显示输出
            if is_done:
                phase_data = st.session_state.phases[phase]
                with st.expander(f"查看 {icon_label} 输出", expanded=(phase == "plan")):
                    output = phase_data.get("output_text", "")
                    st.markdown(output[:8000])

                    # 代码阶段额外显示产物
                    if phase == "code" and st.session_state.artifacts:
                        st.markdown("**生成的文件:**")
                        for art in st.session_state.artifacts:
                            st.caption(f"📄 {art['file_path']}")
                            with st.expander(f"查看 {art['file_path']}"):
                                st.code(art["content"], language=art.get("language", "python"))

    # 全部完成后显示交付
    if all(current_phase_done.values()):
        st.success("🎉 所有阶段已完成！")
        if st.button("📦 保存版本快照", type="primary"):
            # 版本保存通过后端 API
            r = requests.post(
                f"{API_BASE}/api/projects/{proj['id']}/versions",
                json={"message": "三阶段完成"},
                headers=api_headers(),
            )
            if r.status_code == 200:
                st.success("版本快照已保存")
            else:
                st.warning("版本 API 尚未实现")

        if st.button("🆕 开始新项目"):
            st.session_state.current_project = None
            st.session_state.page = "new_project"
            st.rerun()


# ========================================================================
# 版本历史
# ========================================================================

def page_versions():
    proj = st.session_state.current_project
    st.markdown(f"### 📦 版本历史 — {proj['name']}")
    st.caption("Git 风格的文件版本追溯")

    if st.button("↩ 返回工作区"):
        st.session_state.page = "workspace"
        st.rerun()

    # 版本列表
    r = requests.get(
        f"{API_BASE}/api/projects/{proj['id']}/versions",
        headers=api_headers(),
    )
    versions = r.json() if r.status_code == 200 else []

    if not versions:
        st.info("暂无版本记录")
        return

    for v in versions:
        st.markdown(f"""
        <div class="stage-card">
          <span style="font-weight:600;">v{v['version_number']}</span>
          <span style="color:#94a3b8; margin-left:12px;">{v.get('message', '')}</span>
          <span style="color:#64748b; float:right;">{v['created_at'][:19]}</span>
        </div>
        """, unsafe_allow_html=True)


# ========================================================================
# 模板浏览
# ========================================================================

def page_templates():
    st.markdown("### 📦 Agent 团队模板")

    templates = [
        {
            "name": "全栈 Web 应用",
            "id": "full-stack",
            "desc": "经典 4 人团队",
            "roles": [
                ("📋", "ProductManager", "需求分析与技术规划"),
                ("💻", "Engineer", "Python Web 开发"),
                ("🔍", "CodeReviewer", "代码质量与安全检查"),
                ("👤", "UserProxy", "测试验证"),
            ],
        },
        {
            "name": "命令行工具",
            "id": "cli-tool",
            "desc": "精简 3 人团队",
            "roles": [
                ("📋", "ProductManager", "CLI 需求定义"),
                ("💻", "Engineer", "Python CLI 开发"),
                ("🔍", "CodeReviewer", "可用性与错误处理审查"),
            ],
        },
        {
            "name": "API 后端服务",
            "id": "api-service",
            "desc": "专注微服务",
            "roles": [
                ("📋", "ProductManager", "API 设计与数据模型"),
                ("💻", "Engineer", "FastAPI 后端开发"),
                ("🔍", "CodeReviewer", "安全性 & 性能审查"),
            ],
        },
    ]

    for tmpl in templates:
        with st.container():
            st.markdown(f"""
            <div class="stage-card">
              <span style="font-size:18px; font-weight:600;">{tmpl['name']}</span>
              <span style="color:#94a3b8; margin-left:12px;">{tmpl['desc']}</span>
              <div style="margin-top:12px;">
            """, unsafe_allow_html=True)

            for icon, name, desc in tmpl["roles"]:
                st.markdown(f"""
                <span class="role-tag">{icon} {name}</span>
                <small style="color:#64748b;">{desc}</small><br>
                """, unsafe_allow_html=True)

            st.markdown("</div></div>", unsafe_allow_html=True)

    if st.button("↩ 返回项目管理"):
        st.session_state.page = "dashboard"
        st.rerun()


# ========================================================================
# 路由
# ========================================================================

PAGES = {
    "login": page_login,
    "dashboard": page_dashboard,
    "new_project": page_new_project,
    "workspace": page_workspace,
    "versions": page_versions,
    "templates": page_templates,
}

current_page = st.session_state.page
if current_page in PAGES:
    PAGES[current_page]()
else:
    st.session_state.page = "login"
    st.rerun()
