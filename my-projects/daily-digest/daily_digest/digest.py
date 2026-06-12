"""LLM 摘要生成 — 多源内容聚合、分类、生成日报."""

import os
import json
from anthropic import Anthropic
from .sources import Article


DIGEST_SYSTEM_PROMPT = """你是一个专业的信息聚合编辑，负责生成"每日科技日报"。
你的任务是将多条来源的内容整理成一份结构清晰、重点突出的日报。

要求:
- 用中文输出
- 分类别整理 (如: AI/大模型、编程语言/框架、架构/系统设计、科技新闻)
- 每个类别列出 Top 3-5 条，每条 1-2 句话概括
- 最后给出"今日必读"推荐 (2-3条)
- 风格: 专业但不枯燥"""


class DigestGenerator:
    """日报生成器."""

    def __init__(self):
        self._client: Anthropic | None = None

    @property
    def client(self) -> Anthropic:
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv()
            self._client = Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
            )
        return self._client

    @property
    def model(self) -> str:
        return os.getenv("MODEL_ID", "claude-sonnet-4-6")

    # ------------------------------------------------------------------
    # 生成日报
    # ------------------------------------------------------------------

    def generate(self, articles: list[Article],
                 preset_label: str = "科技日报",
                 date_str: str = "",
                 max_articles_for_llm: int = 30) -> str:
        """生成日报 Markdown.

        将文章列表压缩为 LLM 可消化的文本 → LLM 生成分类日报.
        """
        if not articles:
            return f"# {preset_label}\n\n今日无内容。"

        # 构建 LLM 输入
        articles_text = self._format_articles_for_llm(articles[:max_articles_for_llm])
        sources_summary = self._source_distribution(articles)

        prompt = f"""请根据以下内容生成一份{preset_label}。

日期: {date_str or '今天'}
总条目: {len(articles)} 条
来源分布: {sources_summary}

## 采集到的内容

{articles_text}

---

请生成日报 (Markdown格式)，结构如下:

# {preset_label} ({date_str or '今天'})

## 📊 概览
(一句话总结今天的热点和趋势)

## 🤖 AI/大模型
(Top 3-5 条)

## 💻 编程语言/框架
(Top 3-5 条)

## 🏗️ 架构/系统设计
(Top 3-5 条)

## 📡 科技新闻
(Top 3-5 条)

## ⭐ 今日必读
(2-3条最重要的，附URL)

---
*由 Daily Digest Agent 自动生成*"""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=DIGEST_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        result = ""
        for block in response.content:
            if hasattr(block, "text"):
                result += block.text

        return result

    # ------------------------------------------------------------------
    # 简易生成 (不需要 LLM，纯规则聚合)
    # ------------------------------------------------------------------

    @staticmethod
    def generate_simple(articles: list[Article],
                        preset_label: str = "科技日报",
                        date_str: str = "") -> str:
        """简易模式: 按来源分组，不需要 LLM API."""
        from collections import defaultdict

        by_source = defaultdict(list)
        for a in articles:
            by_source[a.source].append(a)

        lines = [
            f"# {preset_label} ({date_str or '今天'})",
            "",
            f"共 {len(articles)} 条内容，来自 {len(by_source)} 个来源",
            "",
        ]

        for source, items in by_source.items():
            lines.append(f"## 📌 {source}")
            lines.append("")
            for a in items[:8]:
                score_info = f" | ⭐{a.score}" if a.score else ""
                comment_info = f" | 💬{a.comments}" if a.comments else ""
                lines.append(f"- [{a.title}]({a.url}){score_info}{comment_info}")
                if a.description:
                    lines.append(f"  > {a.description[:150]}")
            lines.append("")

        lines.append("---")
        lines.append("*由 Daily Digest Agent 自动生成*")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    @staticmethod
    def _format_articles_for_llm(articles: list[Article]) -> str:
        parts = []
        for i, a in enumerate(articles):
            parts.append(f"{i+1}. [{a.source}] {a.title}")
            if a.url:
                parts.append(f"   URL: {a.url}")
            if a.description:
                parts.append(f"   摘要: {a.description[:200]}")
            meta = []
            if a.score:
                meta.append(f"热度={a.score}")
            if a.comments:
                meta.append(f"评论={a.comments}")
            if meta:
                parts.append(f"   {' | '.join(meta)}")
            parts.append("")
        return "\n".join(parts)

    @staticmethod
    def _source_distribution(articles: list[Article]) -> str:
        from collections import Counter
        counts = Counter(a.source for a in articles)
        return ", ".join(f"{k}:{v}条" for k, v in counts.most_common())
