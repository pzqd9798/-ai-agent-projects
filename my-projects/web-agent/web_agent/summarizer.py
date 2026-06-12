"""LLM 摘要生成 — 结构化提取 + 摘要 + 关键要点."""

import json
import os
from dataclasses import dataclass, field
from anthropic import Anthropic

from .extractor import PageContent


@dataclass
class PageReport:
    """完整的页面分析报告."""
    url: str
    title: str
    summary: str = ""                # 300字中文摘要
    key_points: list[str] = field(default_factory=list)  # 关键要点
    page_type: str = ""              # 新闻/博客/文档/产品页/其他
    entities: list[str] = field(default_factory=list)    # 实体 (人名/公司/产品)
    links_of_interest: list[dict] = field(default_factory=list)
    sentiment: str = ""              # 正面/负面/中性
    extraction_method: str = "static"

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "page_type": self.page_type,
            "entities": self.entities,
            "links_of_interest": self.links_of_interest,
            "sentiment": self.sentiment,
            "extraction_method": self.extraction_method,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# {self.title or '无标题'}",
            "",
            f"**URL**: {self.url}  ",
            f"**类型**: {self.page_type} | **立场**: {self.sentiment} | **方法**: {self.extraction_method}",
            "",
            "## 📝 摘要",
            "",
            self.summary,
            "",
            "## 🔑 关键要点",
            "",
        ]
        for p in self.key_points:
            lines.append(f"- {p}")
        if self.entities:
            lines.append("")
            lines.append("## 🏷️ 实体")
            lines.append("")
            lines.append(", ".join(self.entities))
        if self.links_of_interest:
            lines.append("")
            lines.append("## 🔗 相关链接")
            lines.append("")
            for link in self.links_of_interest[:10]:
                lines.append(f"- [{link['text']}]({link['href']})")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM 客户端
# ---------------------------------------------------------------------------

def _get_client() -> Anthropic:
    from dotenv import load_dotenv
    load_dotenv()
    return Anthropic(
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        base_url=os.getenv("ANTHROPIC_BASE_URL") or None,
    )


def _get_model() -> str:
    return os.getenv("MODEL_ID", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# 摘要管道
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """你是一个专业的网页内容分析器。分析以下页面内容，生成结构化报告。

## 页面信息
- URL: {url}
- 标题: {title}
- 元数据: {metadata}

## 页面正文
{text}

## 链接列表 (前50个)
{links}

---

请以严格的 JSON 格式输出（不要markdown代码块，只要JSON）：

{{
  "summary": "300字以内的中文摘要",
  "key_points": ["要点1", "要点2", "要点3", "要点4", "要点5"],
  "page_type": "新闻/博客/文档/产品页/社交/其他",
  "entities": ["实体1"（如果页面提到具体的人名、公司名、产品名等）],
  "links_of_interest": [{{"text": "链接文本", "href": "URL"}}]（选取最有价值的5-10个链接）,
  "sentiment": "正面/负面/中性"
}}

只输出JSON，不要其他内容。"""


def summarize(page: PageContent, custom_prompt: str | None = None) -> PageReport:
    """对页面内容生成结构化摘要报告."""
    client = _get_client()
    model = _get_model()

    # 截断正文以免超出上下文
    max_text = 12000
    text = page.text[:max_text]
    if len(page.text) > max_text:
        text += f"\n... [已截断, 原文{len(page.text)}字符]"

    # 构建链接文本
    links_str = "\n".join(
        f"- {l['text']}: {l['href']}"
        for l in page.links[:50]
    )

    prompt = (custom_prompt or ANALYSIS_PROMPT).format(
        url=page.url,
        title=page.title,
        metadata=json.dumps(page.metadata, ensure_ascii=False),
        text=text,
        links=links_str,
    )

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system="You are a professional web content analyzer. Always output valid JSON.",
        messages=[{"role": "user", "content": prompt}],
    )

    # 提取 LLM 输出的文本
    result_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            result_text += block.text

    # 解析 JSON
    try:
        # 去除可能的 markdown 代码块标记
        result_text = result_text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("\n", 1)[1]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
        data = json.loads(result_text)
    except json.JSONDecodeError:
        data = {
            "summary": result_text[:500],
            "key_points": [],
            "page_type": "未知",
            "entities": [],
            "links_of_interest": [],
            "sentiment": "中性",
        }

    return PageReport(
        url=page.url,
        title=page.title or data.get("title", ""),
        summary=data.get("summary", ""),
        key_points=data.get("key_points", []),
        page_type=data.get("page_type", "未知"),
        entities=data.get("entities", []),
        links_of_interest=data.get("links_of_interest", []),
        sentiment=data.get("sentiment", "中性"),
        extraction_method=page.extraction_method,
    )
