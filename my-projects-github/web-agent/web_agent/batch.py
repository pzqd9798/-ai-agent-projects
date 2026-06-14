"""批量处理 — 并发提取和摘要多个 URL."""

import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from .extractor import extract_static, PageContent
from .summarizer import summarize, PageReport


def process_url(url: str, custom_prompt: str | None = None) -> PageReport | None:
    """处理单个 URL: 提取 + 摘要."""
    try:
        print(f"  [提取] {url}")
        page = extract_static(url)
        print(f"  [分析] {url} ({len(page.text)} chars)")
        report = summarize(page, custom_prompt)
        return report
    except Exception as exc:
        print(f"  [错误] {url}: {exc}")
        return None


def process_batch(
    urls: list[str],
    max_workers: int = 3,
    custom_prompt: str | None = None,
) -> list[PageReport]:
    """并发处理多个 URL.

    Args:
        urls: URL 列表
        max_workers: 并发数 (默认3, 避免触发 rate limit)
        custom_prompt: 自定义分析提示词
    """
    reports = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_url, url, custom_prompt): url
            for url in urls
        }
        for future in as_completed(futures):
            result = future.result()
            if result:
                reports.append(result)
    return reports


async def process_batch_async(
    urls: list[str],
    max_concurrent: int = 3,
    custom_prompt: str | None = None,
) -> list[PageReport]:
    """异步批量处理."""
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        tasks = [
            loop.run_in_executor(executor, process_url, url, custom_prompt)
            for url in urls
        ]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]
