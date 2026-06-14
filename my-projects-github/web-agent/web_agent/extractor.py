"""网页内容提取 — 支持静态HTTP和浏览器两种模式."""

import re
import httpx
from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class PageContent:
    """提取的页面内容."""
    url: str
    title: str = ""
    text: str = ""                     # 清洗后的正文
    raw_html_length: int = 0
    links: list[dict] = field(default_factory=list)  # [{text, href}]
    metadata: dict = field(default_factory=dict)      # {description, keywords, ...}
    extraction_method: str = "static"  # "static" | "browser"


# ---------------------------------------------------------------------------
# 静态提取 (HTTP + BeautifulSoup)
# ---------------------------------------------------------------------------

def extract_static(url: str, timeout: int = 15) -> PageContent:
    """通过 HTTP GET 获取页面, 用 BeautifulSoup 清洗正文."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("请安装 beautifulsoup4: pip install beautifulsoup4")

    resp = httpx.get(
        url, timeout=timeout, follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        },
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    page = PageContent(url=url)

    # 标题
    if soup.title:
        page.title = soup.title.get_text(strip=True)

    # 元数据
    for meta in soup.find_all("meta"):
        name = meta.get("name", meta.get("property", ""))
        content = meta.get("content", "")
        if name and content:
            page.metadata[name] = content

    # 移除无用元素
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # 提取正文
    body = soup.find("body")
    if body:
        text = body.get_text(separator="\n", strip=True)
        # 合并空白行
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        page.text = text

    # 提取链接
    domain = urlparse(url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)
        if text and href and not href.startswith("#"):
            # 处理相对路径
            if href.startswith("/"):
                href = f"https://{domain}{href}"
            elif not href.startswith("http"):
                continue
            page.links.append({"text": text[:200], "href": href})
            if len(page.links) >= 100:
                break

    page.raw_html_length = len(resp.text)
    return page


# ---------------------------------------------------------------------------
# 浏览器提取 (browser-use, 可选)
# ---------------------------------------------------------------------------

async def extract_browser(url: str, task: str | None = None) -> PageContent:
    """通过 browser-use 启动真实浏览器提取 JS 渲染后的内容."""
    try:
        from browser_use.beta import Agent, BrowserProfile, ChatAnthropic
    except ImportError:
        raise ImportError("请安装 browser-use: pip install 'browser-use[core]'")

    domain = urlparse(url).netloc

    extraction_task = task or (
        f"打开 {url}，浏览页面，然后用中文提取："
        "1) 页面标题 2) 正文内容摘要 (300字) 3) 前10个重要链接"
    )

    agent = Agent(
        task=extraction_task,
        llm=ChatAnthropic(model="claude-sonnet-4-6"),
        browser_profile=BrowserProfile(
            headless=True,
            allowed_domains=[f"*.{domain}"],
            wait_for_network_idle_page_load_time=3.0,
        ),
        max_failures=2,
        minimum_wait_page_load_time=0.5,
    )

    history = await agent.run(max_steps=8)
    result = history.final_result() or ""

    return PageContent(
        url=url,
        title=domain,
        text=result,
        extraction_method="browser",
    )
