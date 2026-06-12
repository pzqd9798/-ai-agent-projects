"""浏览器工具 — 将 browser-use 封装为 Agent 工具.

依赖: pip install "browser-use[core]"

封装策略:
    用一个同步函数作为工具 handler,
    内部用 asyncio.run() 启动 browser-use 的 Agent 完成子任务.
    工具接收自然语言任务描述 + URL, 返回提取结果.
"""

from app.engine.tool_registry import register_tool


async def _browse_async(url: str, task: str, headless: bool = True) -> str:
    """异步执行 browser-use Agent."""
    try:
        from browser_use.beta import Agent, BrowserProfile, ChatAnthropic
    except ImportError:
        return "错误: 请安装 browser-use: pip install 'browser-use[core]'"

    domain = url.split("/")[2] if "//" in url else url.split("/")[0]

    try:
        agent = Agent(
            task=task,
            llm=ChatAnthropic(model="claude-sonnet-4-6"),
            browser_profile=BrowserProfile(
                headless=headless,
                allowed_domains=[f"*.{domain}"],
                wait_for_network_idle_page_load_time=2.0,
            ),
            max_failures=2,
        )
        history = await agent.run(max_steps=10)
        return history.final_result() or "[无结果]"
    except Exception as exc:
        return f"浏览器操作失败: {exc}"


def tool_browse_web(url: str, task: str = "提取本页核心内容并生成摘要") -> str:
    """浏览器工具入口 (同步)."""
    import asyncio
    try:
        return asyncio.run(_browse_async(url, task))
    except Exception as exc:
        return f"错误: {exc}"


register_tool("browse_web", (
    "打开网页并用浏览器自动化工具执行任务。"
    "用于需要 JavaScript 渲染、表单交互或复杂导航的页面。"
    "task 参数用中文描述你要做什么（如'提取页面标题和所有链接'）。"
), {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "目标网页 URL。"},
        "task": {"type": "string", "description": "要执行的任务描述（中文）。默认提取核心内容并生成摘要。"},
    },
    "required": ["url"],
}, tool_browse_web)
