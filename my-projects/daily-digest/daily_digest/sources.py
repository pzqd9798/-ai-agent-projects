"""多源数据采集 — Hacker News, GitHub Trending, 知乎热榜, RSS, 自定义网页."""

import re
import httpx
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Article:
    """统一的内容条目."""
    title: str
    url: str = ""
    description: str = ""       # 摘要/简介
    source: str = ""            # 来源名称
    score: int = 0              # 热度分数
    comments: int = 0           # 评论数
    author: str = ""
    tags: list[str] = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_text(self) -> str:
        """可读的文本表示."""
        parts = [f"## {self.title}"]
        if self.url:
            parts.append(f"链接: {self.url}")
        if self.description:
            parts.append(self.description)
        meta = []
        if self.score:
            meta.append(f"热度: {self.score}")
        if self.comments:
            meta.append(f"评论: {self.comments}")
        if self.author:
            meta.append(f"作者: {self.author}")
        if meta:
            parts.append(" | ".join(meta))
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# 通用 HTTP 客户端
# ---------------------------------------------------------------------------

_client = httpx.Client(
    timeout=15,
    follow_redirects=True,
    headers={"User-Agent": "DailyDigest/1.0"},
)


# ---------------------------------------------------------------------------
# 1. Hacker News
# ---------------------------------------------------------------------------

def fetch_hackernews(max_items: int = 15) -> list[Article]:
    """获取 Hacker News 首页热门."""
    try:
        # 获取 top stories IDs
        resp = _client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        ids = resp.json()[:max_items]

        articles = []
        for item_id in ids:
            try:
                item = _client.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
                ).json()
                if item and item.get("title"):
                    articles.append(Article(
                        title=item.get("title", ""),
                        url=item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                        score=item.get("score", 0),
                        comments=item.get("descendants", 0),
                        author=item.get("by", ""),
                        source="Hacker News",
                    ))
            except Exception:
                continue
        return articles
    except Exception as exc:
        print(f"  [HN] 获取失败: {exc}")
        return []


# ---------------------------------------------------------------------------
# 2. GitHub Trending
# ---------------------------------------------------------------------------

def fetch_github_trending(language: str = "", max_items: int = 10) -> list[Article]:
    """获取 GitHub Trending 仓库 (通过非官方API)."""
    try:
        resp = _client.get("https://api.github.com/search/repositories", params={
            "q": f"created:>{_today_str()}" + (f" language:{language}" if language else ""),
            "sort": "stars",
            "order": "desc",
            "per_page": max_items,
        })
        data = resp.json()
        articles = []
        for repo in data.get("items", []):
            articles.append(Article(
                title=repo.get("full_name", ""),
                url=repo.get("html_url", ""),
                description=repo.get("description", "") or "",
                score=repo.get("stargazers_count", 0),
                author=repo.get("owner", {}).get("login", "") if repo.get("owner") else "",
                tags=[repo.get("language", "")] if repo.get("language") else [],
                source="GitHub Trending",
            ))
        return articles
    except Exception as exc:
        print(f"  [GitHub] 获取失败: {exc}")
        return []


# ---------------------------------------------------------------------------
# 3. 知乎热榜
# ---------------------------------------------------------------------------

def fetch_zhihu_hot(max_items: int = 15) -> list[Article]:
    """获取知乎热榜."""
    try:
        resp = _client.get("https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total",
                           params={"limit": max_items})
        data = resp.json()
        articles = []
        for item in data.get("data", []):
            target = item.get("target", {})
            articles.append(Article(
                title=target.get("title", ""),
                url=f"https://www.zhihu.com/question/{target.get('id', '')}",
                description=target.get("excerpt", "")[:300] or "",
                score=target.get("detail_count", 0) or item.get("detail_count", 0) or 0,
                source="知乎热榜",
                tags=[t.get("name", "") for t in target.get("children", [])[:3]],
            ))
        return articles
    except Exception as exc:
        print(f"  [知乎] 获取失败: {exc}")
        return []


# ---------------------------------------------------------------------------
# 4. RSS 订阅源
# ---------------------------------------------------------------------------

DEFAULT_RSS_FEEDS = {
    "机器之心": "https://feeds.feedburner.com/jiqizhixin",
    "InfoQ中文": "https://www.infoq.cn/feed",
    "Dev.to": "https://dev.to/feed",
}


def fetch_rss(feed_url: str, source_label: str = "",
              max_items: int = 10) -> list[Article]:
    """获取 RSS 订阅源."""
    try:
        import feedparser
    except ImportError:
        print("  [RSS] 请安装 feedparser: pip install feedparser")
        return []

    try:
        feed = feedparser.parse(feed_url)
        articles = []
        for entry in feed.entries[:max_items]:
            articles.append(Article(
                title=entry.get("title", ""),
                url=entry.get("link", ""),
                description=_strip_html(entry.get("summary", entry.get("description", "")))[:300],
                author=entry.get("author", ""),
                source=source_label or feed_url,
                tags=[t.get("term", "") for t in entry.get("tags", [])],
            ))
        return articles
    except Exception as exc:
        print(f"  [RSS:{source_label}] 获取失败: {exc}")
        return []


def fetch_rss_feeds(feeds: dict[str, str] | None = None) -> list[Article]:
    """批量获取 RSS 订阅源."""
    feeds = feeds or DEFAULT_RSS_FEEDS
    all_articles = []
    for label, url in feeds.items():
        print(f"  📡 RSS: {label}")
        articles = fetch_rss(url, label)
        all_articles.extend(articles)
        print(f"     {len(articles)} 条")
    return all_articles


# ---------------------------------------------------------------------------
# 5. 自定义网页 (静态提取)
# ---------------------------------------------------------------------------

def fetch_webpage(url: str, source_label: str = "",
                  link_selector: str = "a[href]",
                  max_items: int = 10) -> list[Article]:
    """从任意网页提取链接列表."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("  [Web] 请安装 beautifulsoup4: pip install beautifulsoup4")
        return []

    try:
        resp = _client.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")

        articles = []
        for link in soup.select(link_selector)[:max_items]:
            href = link.get("href", "")
            text = link.get_text(strip=True)
            if text and href and len(text) > 5:
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                articles.append(Article(
                    title=text,
                    url=href,
                    source=source_label or url,
                ))
        return articles
    except Exception as exc:
        print(f"  [Web:{source_label}] 获取失败: {exc}")
        return []


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text)


# ---------------------------------------------------------------------------
# 批量采集
# ---------------------------------------------------------------------------

# 预定义采集计划
PRESETS = {
    "tech": {
        "sources": ["hackernews", "github", "devto"],
        "label": "科技日报",
    },
    "china": {
        "sources": ["zhihu", "infoq", "jiqizhixin"],
        "label": "国内科技日报",
    },
    "full": {
        "sources": ["hackernews", "github", "zhihu", "rss"],
        "label": "综合日报",
    },
}


def collect_all(preset: str = "tech", extra_feeds: dict[str, str] | None = None,
                max_per_source: int = 10) -> list[Article]:
    """按预设采集所有来源."""
    config = PRESETS.get(preset, PRESETS["tech"])
    print(f"📊 采集计划: {config['label']}")

    all_articles: list[Article] = []

    for source in config["sources"]:
        print(f"  🔍 {source}...")
        if source == "hackernews":
            all_articles.extend(fetch_hackernews(max_per_source))
        elif source == "github":
            all_articles.extend(fetch_github_trending(max_items=max_per_source))
        elif source == "zhihu":
            all_articles.extend(fetch_zhihu_hot(max_per_source))
        elif source == "rss":
            all_articles.extend(fetch_rss_feeds(extra_feeds))
        elif source == "devto":
            all_articles.extend(fetch_rss("https://dev.to/feed", "Dev.to", max_per_source))
        elif source == "infoq":
            all_articles.extend(fetch_rss("https://www.infoq.cn/feed", "InfoQ", max_per_source))
        elif source == "jiqizhixin":
            all_articles.extend(fetch_rss("https://feeds.feedburner.com/jiqizhixin", "机器之心", max_per_source))

    # 按热度排序
    all_articles.sort(key=lambda a: a.score, reverse=True)
    return all_articles
