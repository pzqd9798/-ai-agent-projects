"""Daily Digest — 信息聚合日报.

用法:
    # 立即生成
    python -m daily_digest now                     # 简易模式 (无需API key)
    python -m daily_digest now --preset full       # 综合日报 + LLM 生成

    # 定时调度
    python -m daily_digest schedule --now          # 立即 + 持续
    python -m daily_digest schedule --cron "0 8 * * *"  # 每天8点

    # 推送 Telegram
    python -m daily_digest now -t $BOT_TOKEN -c $CHAT_ID

    # 测试 RSS
    python -m daily_digest feeds --list
    python -m daily_digest feeds -u https://example.com/feed.xml
"""

from .cli import main

if __name__ == "__main__":
    main()
