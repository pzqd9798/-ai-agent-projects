"""Web Agent — Streamlit 前端.

启动: streamlit run frontend.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from web_agent.extractor import extract_static
from web_agent.summarizer import summarize

st.set_page_config(page_title="Web Agent", page_icon="🌐", layout="wide")

st.title("🌐 Web Agent")
st.caption("智能网页采集 · 双模提取 · AI 摘要")

# ── 输入区 ──
c1, c2 = st.columns([4, 1])
with c1:
    url = st.text_input("URL", placeholder="https://example.com")
with c2:
    go = st.button("🔍 提取 & 分析", type="primary", use_container_width=True)

if go and url:
    with st.spinner("📡 提取页面内容..."):
        try:
            page = extract_static(url)
        except Exception as e:
            st.error(f"提取失败: {e}")
            st.stop()

    col1, col2, col3 = st.columns(3)
    col1.metric("标题", page.title[:30] if page.title else "无标题")
    col2.metric("正文长度", f"{len(page.text):,} 字符")
    col3.metric("链接数", len(page.links))

    with st.spinner("🧠 AI 生成摘要..."):
        try:
            report = summarize(page)
        except Exception as e:
            st.warning(f"LLM 摘要失败 ({e})，显示原始内容")
            st.text(page.text[:3000])
            st.stop()

    # ── 结果 ──
    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("页面类型", report.page_type)
    c2.metric("情感倾向", report.sentiment)
    c3.metric("实体数", len(report.entities))
    c4.metric("提取方式", report.extraction_method)

    st.markdown("---")
    st.markdown(f"## 📝 {report.title or '页面摘要'}")

    if report.summary:
        st.markdown(report.summary)

    if report.key_points:
        st.markdown("### 🔑 关键要点")
        for p in report.key_points:
            st.markdown(f"- {p}")

    if report.entities:
        st.markdown(f"**🏷️ 实体**: {', '.join(report.entities)}")

    if report.links_of_interest:
        st.markdown("### 🔗 相关链接")
        for link in report.links_of_interest[:10]:
            st.markdown(f"- [{link['text']}]({link['href']})")
