"""web-agent 桥接 — 将 web-agent 项目集成到 agent-platform 工具系统.

依赖: 确保 web-agent 在 Python path 中:
    pip install -e ../web-agent
    # 或
    export PYTHONPATH="../web-agent:$PYTHONPATH"
"""

from app.engine.tool_registry import register_tool


def _import_web_agent():
    """延迟导入 web-agent，缺失时给出友好提示."""
    try:
        from web_agent.extractor import extract_static
        from web_agent.summarizer import summarize
        return extract_static, summarize
    except ImportError:
        raise ImportError(
            "web-agent 未安装。运行: pip install -e ../web-agent"
        )


def tool_web_summary(url: str) -> str:
    """提取网页内容并生成结构化摘要."""
    try:
        extract_static, summarize = _import_web_agent()
        page = extract_static(url)
        report = summarize(page)
        return report.to_markdown()
    except ImportError as e:
        return str(e)
    except Exception as e:
        return f"网页摘要失败: {e}"


register_tool("web_summary", (
    "获取公开网页内容并生成结构化摘要报告。"
    "输出包含标题、摘要、关键要点、页面类型、实体和情感倾向。"
    "用于快速了解网页内容，无需打开浏览器。"
), {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "目标网页 URL。"},
    },
    "required": ["url"],
}, tool_web_summary)
