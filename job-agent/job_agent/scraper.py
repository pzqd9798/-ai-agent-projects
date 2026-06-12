"""职位搜索爬虫 — 基于 browser-use 的浏览器自动化.

支持多站点: LinkedIn Jobs, Indeed, Glassdoor.
自动搜索职位 → 浏览列表 → 逐个提取 JD 详情.
"""

import asyncio
from urllib.parse import quote
from .models import JobListing, JobSearchResult


# 搜索站点配置
SITES = {
    "linkedin": {
        "name": "LinkedIn",
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}",
    },
    "indeed": {
        "name": "Indeed",
        "search_url": "https://www.indeed.com/jobs?q={keyword}&l={location}",
    },
    "glassdoor": {
        "name": "Glassdoor",
        "search_url": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keyword}&sc.location={location}",
    },
}


async def _browse_search(site_url: str, keyword: str, site_domain: str,
                         max_jobs: int = 10) -> list[JobListing]:
    """用 browser-use 执行一次搜索 + 提取."""
    try:
        from browser_use.beta import Agent, BrowserProfile, ChatAnthropic
        import os
    except ImportError:
        raise ImportError("请安装 browser-use: pip install 'browser-use[core]'")

    task = f"""你是一个专业的职位搜索助手。按以下步骤操作:

1. 打开职位搜索页面: {site_url}
2. 等待页面完全加载 (包含 JavaScript 渲染的职位列表)
3. 浏览职位列表，对前 {max_jobs} 个职位，逐个点击查看详情
4. 对每个职位提取以下信息:
   - 职位名称 (title)
   - 公司名称 (company)
   - 工作地点 (location)
   - 职位描述 (description) — 提取前500字
   - 薪资范围 (salary) — 如果有的话
   - 发布日期 (posted_date) — 如果有的话

5. 提取完成后，用中文输出结构化的职位列表。每个职位用以下格式:
   [职位名称] @ [公司] | [地点] | [薪资]
   [前200字描述...]
   ---

注意:
- 关键词: "{keyword}"
- 如果页面要求登录或验证，说明无法继续
- 不要填写任何表单、不要提交个人信息
- 提取完 {max_jobs} 个或页面不再有新职位时停止
"""

    domain = site_url.split("/")[2]
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    agent = Agent(
        task=task,
        llm=ChatAnthropic(model=os.getenv("MODEL_ID", "claude-sonnet-4-6")),
        browser_profile=BrowserProfile(
            headless=True,
            allowed_domains=[f"*.{domain}"],
            wait_for_network_idle_page_load_time=3.0,
        ),
        max_failures=3,
        minimum_wait_page_load_time=1.0,
    )

    history = await agent.run(max_steps=20)
    result_text = history.final_result() or ""

    # 解析 browser-use 输出为 JobListing 列表
    listings = _parse_llm_output(result_text, keyword, site_domain)
    return listings


def _parse_llm_output(text: str, keyword: str, source: str) -> list[JobListing]:
    """将 LLM 输出解析为 JobListing 列表."""
    listings = []
    # 按 --- 分割
    blocks = text.split("---")
    for block in blocks:
        block = block.strip()
        if not block or len(block) < 20:
            continue

        lines = block.split("\n")
        first_line = lines[0] if lines else ""

        # 尝试解析第一行: [职位] @ [公司] | [地点] | [薪资]
        title, company, location, salary = "", "", "", ""

        if " @ " in first_line:
            parts = first_line.split(" @ ", 1)
            title = parts[0].strip().lstrip("[").rstrip("]").strip()
            rest = parts[1] if len(parts) > 1 else ""
            if " | " in rest:
                meta = rest.split(" | ")
                company = meta[0].strip()
                if len(meta) > 1:
                    location = meta[1].strip()
                if len(meta) > 2:
                    salary = meta[2].strip()
            else:
                company = rest.strip()
        elif first_line.startswith("["):
            m = __import__("re").match(r"\[(.+?)\]\s*(.*)", first_line)
            if m:
                title = m.group(1)
                company = m.group(2).strip()

        description = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""

        if title:
            listings.append(JobListing(
                title=title,
                company=company,
                location=location,
                salary=salary,
                description=description[:2000],
                source=source,
            ))

    return listings


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------

async def search_jobs_async(
    keyword: str,
    location: str = "",
    sites: list[str] | None = None,
    max_per_site: int = 10,
) -> JobSearchResult:
    """异步搜索职位."""
    sites = sites or ["linkedin"]
    all_listings: list[JobListing] = []

    for site_key in sites:
        config = SITES.get(site_key)
        if not config:
            print(f"未知站点: {site_key}")
            continue

        url = config["search_url"].format(
            keyword=quote(keyword),
            location=quote(location or ""),
        )
        print(f"🔍 搜索 {config['name']}: {keyword}")
        try:
            listings = await _browse_search(url, keyword, site_key, max_per_site)
            all_listings.extend(listings)
            print(f"   找到 {len(listings)} 个职位")
        except ImportError as e:
            print(f"   browser-use 未安装: {e}")
            raise
        except Exception as exc:
            print(f"   {config['name']} 搜索失败: {exc}")

    return JobSearchResult(
        keyword=keyword,
        location=location,
        total_found=len(all_listings),
        listings=all_listings,
    )


def search_jobs(
    keyword: str,
    location: str = "",
    sites: list[str] | None = None,
    max_per_site: int = 10,
) -> JobSearchResult:
    """同步搜索职位 (封装 asyncio)."""
    return asyncio.run(search_jobs_async(keyword, location, sites, max_per_site))
