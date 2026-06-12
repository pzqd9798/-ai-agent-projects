"""CLI — 信息聚合日报命令行界面."""

import sys
import argparse
from datetime import datetime
from pathlib import Path


def cmd_now(args):
    """立即生成一份日报."""
    from .sources import collect_all
    from .digest import DigestGenerator

    date_str = datetime.now().strftime("%Y-%m-%d")
    print(f"\n{'='*50}")
    print(f"  Daily Digest — {date_str}")
    print(f"{'='*50}\n")

    # 1. 采集
    print("📡 采集数据...\n")
    articles = collect_all(preset=args.preset, max_per_source=args.max)

    if not articles:
        print("❌ 未采集到任何内容。请检查网络连接。")
        sys.exit(1)

    print(f"\n✅ 采集完成: {len(articles)} 条")
    for article in articles[:5]:
        print(f"   [{article.source}] {article.title[:60]}")

    # 2. 生成
    date_str = datetime.now().strftime("%Y-%m-%d")

    if args.simple:
        print(f"\n📝 生成简易日报 (无LLM)...")
        digest = DigestGenerator.generate_simple(articles, args.preset, date_str)
    else:
        print(f"\n🧠 LLM 生成日报...")
        try:
            gen = DigestGenerator()
            digest = gen.generate(articles, args.preset, date_str)
        except Exception as exc:
            print(f"   LLM 失败 ({exc})，降级为简易模式")
            digest = DigestGenerator.generate_simple(articles, args.preset, date_str)

    # 3. 输出
    print(f"\n{'='*50}\n")
    print(digest)

    # 4. 保存
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_file = out_dir / f"digest_{date_str}.md"
    md_file.write_text(digest, encoding="utf-8")
    print(f"\n💾 已保存: {md_file}")

    # 5. 推送 Telegram
    if args.telegram:
        import os
        token = args.telegram or os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = args.chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
        if token and chat_id:
            from .notify import send_telegram_sync
            print(f"📤 推送到 Telegram...")
            ok = send_telegram_sync(token, chat_id, digest)
            if ok:
                print("   ✅ 推送成功")
            else:
                print("   ❌ 推送失败")


def cmd_schedule(args):
    """启动定时调度."""
    from .scheduler import DailyScheduler, create_scheduled_runner

    runner = create_scheduled_runner(
        preset=args.preset,
        output_dir=args.output,
        telegram_token=args.telegram or "",
        telegram_chat_id=args.chat_id or "",
        use_llm=not args.simple,
    )

    if args.now:
        runner()
        if not args.cron and not args.interval:
            return

    scheduler = DailyScheduler(
        callback=runner,
        interval_seconds=args.interval,
        cron_expr=args.cron,
    )
    try:
        scheduler.start()
        print("按 Ctrl+C 停止...")
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        scheduler.stop()
        print("\n再见。")


def cmd_feeds(args):
    """测试 RSS 订阅源."""
    from .sources import fetch_rss_feeds

    if args.list:
        from .sources import DEFAULT_RSS_FEEDS
        print("默认 RSS 订阅源:")
        for label, url in DEFAULT_RSS_FEEDS.items():
            print(f"  {label}: {url}")
        return

    if args.url:
        from .sources import fetch_rss
        articles = fetch_rss(args.url, args.label or args.url)
    else:
        articles = fetch_rss_feeds()

    for a in articles:
        print(f"[{a.source}] {a.title}")
        if a.description:
            print(f"  {a.description[:150]}")
        print(f"  {a.url}")
        print()


def main():
    parser = argparse.ArgumentParser(description="📰 Daily Digest — 信息聚合日报")

    sub = parser.add_subparsers(dest="cmd")

    # now — 立即生成
    now = sub.add_parser("now", help="立即生成日报", aliases=["n"])
    now.add_argument("--preset", "-p", default="tech",
                     choices=["tech", "china", "full"], help="采集计划")
    now.add_argument("--max", "-m", type=int, default=10, help="每源最大条目")
    now.add_argument("--simple", "-S", action="store_true", help="简易模式 (无需LLM)")
    now.add_argument("--output", "-o", default="./output", help="输出目录")
    now.add_argument("--telegram", "-t", default="", help="Telegram Bot Token")
    now.add_argument("--chat-id", "-c", default="", help="Telegram Chat ID")

    # schedule — 定时调度
    sched = sub.add_parser("schedule", help="定时运行", aliases=["s"])
    sched.add_argument("--preset", "-p", default="tech", choices=["tech", "china", "full"])
    sched.add_argument("--cron", default="", help="Cron表达式, 如 '0 8 * * *'")
    sched.add_argument("--interval", "-i", type=int, default=0, help="间隔秒数")
    sched.add_argument("--now", action="store_true", help="先立即执行一次")
    sched.add_argument("--simple", "-S", action="store_true", help="简易模式")
    sched.add_argument("--output", "-o", default="./output", help="输出目录")
    sched.add_argument("--telegram", "-t", default="")
    sched.add_argument("--chat-id", "-c", default="")

    # feeds — 测试 RSS
    feeds = sub.add_parser("feeds", help="测试 RSS 源", aliases=["f"])
    feeds.add_argument("--list", "-l", action="store_true", help="列出默认订阅源")
    feeds.add_argument("--url", "-u", default="", help="测试单个 RSS URL")
    feeds.add_argument("--label", default="", help="来源标签")

    args = parser.parse_args()

    if args.cmd in ("now", "n"):
        cmd_now(args)
    elif args.cmd in ("schedule", "s"):
        cmd_schedule(args)
    elif args.cmd in ("feeds", "f"):
        cmd_feeds(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
