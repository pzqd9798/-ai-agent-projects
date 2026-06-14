#!/usr/bin/env python3
"""Web Agent — 智能网页信息采集工具.

用法:
    # 单个网页
    python -m web_agent fetch https://example.com
    python -m web_agent fetch https://example.com -o json
    python -m web_agent fetch https://example.com --browser

    # 批量处理
    python -m web_agent batch https://a.com https://b.com
    python -m web_agent batch --file urls.txt -w 5

    # Python API
    from web_agent.extractor import extract_static
    from web_agent.summarizer import summarize
    page = extract_static("https://example.com")
    report = summarize(page)
"""

from .cli import main

if __name__ == "__main__":
    main()
