"""Daily Digest — Streamlit 前端.

启动: streamlit run frontend.py
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
from daily_digest.sources import collect_all
from daily_digest.digest import DigestGenerator

PRESETS = {
    "tech": "科技日报 — HN + GitHub + Dev.to",
    "china": "国内科技日报 — 知乎 + InfoQ + 机器之心",
    "full": "综合日报 — 全部数据源",
}

st.set_page_config(page_title="Daily Digest", page_icon="📰", layout="wide")

for key in ["generate", "articles", "overall", "show_history", "history_content"]:
    if key not in st.session_state:
        st.session_state[key] = False if key in ("generate", "show_history") else "" if key in ("overall", "history_content") else []

with st.sidebar:
    st.title("📰 Daily Digest")

    preset = st.selectbox("采集计划", list(PRESETS.keys()),
                          format_func=lambda x: f"{x} — {PRESETS[x].split('—')[1].strip()}")

    mode = st.radio("生成模式", ["🧠 LLM 智能分类", "📝 简易（按来源分组）"], index=0)
    use_llm = mode.startswith("🧠")

    st.divider()

    if st.button("⚡ 立即生成", type="primary", use_container_width=True):
        st.session_state.generate = True

    output_dir = Path("output")
    saved = sorted(output_dir.glob("digest_*.md"), reverse=True)
    if saved:
        st.divider()
        st.markdown(f"**📚 历史日报** ({len(saved)} 份)")
        for f in saved[:10]:
            date_label = f.stem.replace("digest_", "")
            if st.button(f"📄 {date_label}", key=f"hist_{f.name}"):
                st.session_state.history_content = f.read_text(encoding="utf-8")
                st.session_state.show_history = True
                st.session_state.generate = False
                st.rerun()

st.title("📰 Daily Digest")
st.caption("多源信息聚合 · AI 分类整理 · 每日科技日报")

if st.session_state.get("show_history") and st.session_state.get("history_content"):
    if st.button("← 返回"):
        st.session_state.show_history = False
        st.rerun()
    st.markdown("---")
    st.markdown(st.session_state.history_content)
    st.stop()

if st.session_state.get("generate"):
    with st.spinner("📡 采集数据中..."):
        articles = collect_all(preset=preset, max_per_source=10)

    if not articles:
        st.error("未采集到内容，请检查网络")
    else:
        col1, col2 = st.columns(2)
        col1.metric("采集条目", len(articles))
        col2.metric("数据来源", len(set(a.source for a in articles)))

        date_str = datetime.now().strftime("%Y-%m-%d")

        with st.spinner("🤖 生成日报..." if use_llm else "📝 整理中..."):
            if use_llm:
                try:
                    gen = DigestGenerator()
                    digest = gen.generate(articles, preset, date_str)
                except Exception as e:
                    st.warning(f"LLM 失败 ({e})，降级为简易模式")
                    digest = DigestGenerator.generate_simple(articles, preset, date_str)
            else:
                digest = DigestGenerator.generate_simple(articles, preset, date_str)

        st.markdown("---")
        st.markdown(digest)

        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        filepath = output_dir / f"digest_{date_str}.md"
        filepath.write_text(digest, encoding="utf-8")
        st.success(f"已保存 → {filepath}")

    st.session_state.generate = False
