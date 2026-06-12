"""CLI — 求职助手命令行界面."""

import sys
import argparse
from pathlib import Path
from .reporter import print_rich, to_markdown, to_json


def cmd_demo(args):
    """演示模式 — 无需 browser-use 和 API key."""
    from .demo import demo_match_batch
    print("🎯 求职助手 — 演示模式\n")

    report = demo_match_batch()
    _output_report(report, args)


def cmd_search(args):
    """真实搜索 + LLM 匹配."""
    from .models import Resume
    from .matcher import JobMatcher

    # 加载简历
    if args.resume:
        resume_text = Path(args.resume).read_text(encoding="utf-8")
        resume = Resume(raw_text=resume_text)
        # 简单解析
        for line in resume_text.split("\n"):
            line = line.strip()
            if line.startswith("技能") or line.startswith("Skills"):
                skills = line.split("：")[-1] if "：" in line else line.split(":")[-1]
                resume.skills = [s.strip() for s in skills.replace("/", ",").split(",") if s.strip()]
    else:
        from .demo import create_demo_resume
        resume = create_demo_resume()
        print("使用演示简历 (--resume 可指定简历文件)\n")

    # 搜索
    print(f"🔍 搜索关键词: {args.keyword}\n")

    try:
        from .scraper import search_jobs
        search_result = search_jobs(
            keyword=args.keyword,
            location=args.location or "",
            sites=args.sites.split(",") if args.sites else ["linkedin"],
            max_per_site=args.max,
        )
    except ImportError:
        print("browser-use 未安装，无法搜索。请: pip install 'browser-use[core]'")
        print("你可以用 --demo 试试演示模式")
        sys.exit(1)

    if not search_result.listings:
        print("未找到职位。试试其他关键词或站点。")
        sys.exit(0)

    # 匹配
    print(f"\n🧠 LLM 匹配中 ({len(search_result.listings)} 个职位)...\n")
    matcher = JobMatcher()
    report = matcher.match_batch(resume, search_result, max_jobs=args.max)

    _output_report(report, args)


def _output_report(report, args):
    if args.output == "json":
        print(to_json(report))
    elif args.output == "md":
        print(to_markdown(report))
    else:
        print_rich(report)

    if args.save:
        out = Path(args.save)
        content = to_json(report) if out.suffix == ".json" else to_markdown(report)
        out.write_text(content, encoding="utf-8")
        print(f"\n💾 已保存: {out}")


def main():
    parser = argparse.ArgumentParser(description="🎯 求职助手 — 自动搜索职位并匹配简历")

    sub = parser.add_subparsers(dest="cmd")

    # demo 子命令
    demo = sub.add_parser("demo", help="演示模式 (不需要 browser-use 和 API key)")
    demo.add_argument("--output", "-o", default="rich", choices=["rich", "md", "json"])
    demo.add_argument("--save", "-s", help="保存报告到文件")

    # search 子命令
    search = sub.add_parser("search", help="搜索职位并匹配")
    search.add_argument("keyword", help="搜索关键词，如 'Python后端'")
    search.add_argument("--location", "-l", default="", help="地点，如 '北京'")
    search.add_argument("--sites", default="linkedin", help="搜索站点 (linkedin,indeed,glassdoor)")
    search.add_argument("--max", "-m", type=int, default=10, help="最大职位数")
    search.add_argument("--resume", "-r", help="简历文件路径 (TXT)")
    search.add_argument("--output", "-o", default="rich", choices=["rich", "md", "json"])
    search.add_argument("--save", "-s", help="保存报告到文件")

    args = parser.parse_args()

    if args.cmd == "demo":
        cmd_demo(args)
    elif args.cmd == "search":
        cmd_search(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
