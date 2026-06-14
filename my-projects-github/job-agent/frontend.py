"""求职助手 — Streamlit 前端.

启动: streamlit run frontend.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from job_agent.demo import demo_match_batch, SAMPLE_JOBS, SAMPLE_RESUME, demo_match
from job_agent.models import Resume

st.set_page_config(page_title="求职助手", page_icon="🎯", layout="wide")

# ── 侧边栏：简历 ──
with st.sidebar:
    st.title("🎯 求职助手")
    st.caption("职位匹配 · 简历评分 · 投递建议")

    st.subheader("📋 简历")
    resume_mode = st.radio("简历来源", ["使用示例简历", "粘贴简历文本"], index=0)

    if resume_mode == "使用示例简历":
        resume = SAMPLE_RESUME
        st.info(f"示例: {resume.name} | {', '.join(resume.skills[:5])}...")
    else:
        resume_text = st.text_area("粘贴简历", height=200,
                                   placeholder="姓名：...\n技能：Python, FastAPI, ...\n经历：...")
        resume = Resume(raw_text=resume_text)
        # 简单解析技能
        for line in resume_text.split("\n"):
            if "技能" in line or "skill" in line.lower():
                skills = line.split("：")[-1] if "：" in line else line.split(":")[-1]
                resume.skills = [s.strip() for s in skills.replace("/", ",").split(",") if s.strip()]
        if not resume.skills:
            resume.skills = SAMPLE_RESUME.skills

    st.divider()

    st.subheader("📊 职位数据")
    job_source = st.radio("数据来源", ["演示数据（8个模拟职位）", "真实搜索（browser-use）"], index=0)

    if job_source.startswith("演示"):
        search_result = None  # 用 demo_match
    else:
        st.caption("需要 browser-use + API key")
        search_result = None

    st.divider()

    if st.button("🎯 开始匹配", type="primary", use_container_width=True):
        st.session_state.match = True

# ── 主区域 ──
st.title("🎯 求职助手")
st.caption("自动匹配职位 · 多维度评分 · 投递建议")

if st.session_state.get("match"):
    with st.spinner("📊 分析匹配中..."):
        if job_source.startswith("演示"):
            if resume_mode == "使用示例简历":
                report = demo_match_batch()
            else:
                from job_agent.demo import create_demo_search_result
                sr = create_demo_search_result()
                matches = [demo_match(resume, job) for job in sr.listings]
                from job_agent.models import MatchReport
                report = MatchReport(resume=resume, search_result=sr, matches=matches)
        else:
            st.warning("真实搜索需要配置 browser-use 和 API key，使用演示数据代替")
            report = demo_match_batch()

    # 显示结果
    top = report.sorted_matches()

    st.markdown("---")

    # 统计条
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("匹配职位", len(top))
    c2.metric("强推", sum(1 for m in top if m.apply_recommendation == "强推"))
    c3.metric("推荐", sum(1 for m in top if m.apply_recommendation == "推荐"))
    avg = sum(m.overall_score for m in top) / len(top) if top else 0
    c4.metric("平均分", f"{avg:.0f}")

    st.markdown("---")

    # 排名卡片
    for i, m in enumerate(top):
        color_map = {"强推": "#4ade80", "推荐": "#fbbf24", "可投": "#f97316", "不推荐": "#ef4444"}
        color = color_map.get(m.apply_recommendation, "#94a3b8")

        with st.container():
            st.markdown(
                f'<div style="background:#1e293b;border-left:4px solid {color};'
                f'border-radius:0 12px 12px 0;padding:20px;margin-bottom:16px">'
                f'<span style="font-size:20px;font-weight:700;color:#e2e8f0">'
                f'#{i+1} {m.job.title}</span>'
                f'<span style="float:right;font-size:24px;font-weight:700;color:{color}">'
                f'{m.overall_score}%</span><br>'
                f'<span style="color:#94a3b8">{m.job.company} · {m.job.location} · {m.job.salary or "薪资面议"}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**✅ 匹配技能**: {', '.join(m.skill_match) if m.skill_match else '无'}")
                st.markdown(f"**💪 优势**: {'; '.join(m.strengths) if m.strengths else '无'}")
            with c2:
                st.markdown(f"**⚠️ 技能差距**: {', '.join(m.skill_gaps) if m.skill_gaps else '无'}")
                st.markdown(f"**📝 建议**: {m.suggestions}")

            st.caption(f"推荐: **{m.apply_recommendation}** | {m.experience_match}")
            st.markdown("---")

    # 保存
    from job_agent.reporter import to_markdown
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    from datetime import datetime
    report_md = to_markdown(report)
    filepath = output_dir / f"match_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath.write_text(report_md, encoding="utf-8")
    st.success(f"已保存 → {filepath}")

    st.session_state.match = False
