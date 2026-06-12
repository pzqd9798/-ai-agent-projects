"""CLI — 基于 Rich 的终端交互界面."""

import sys
import json
import argparse
from pathlib import Path
from typing import Any

from .extractor import extract_static
from .summarizer import summarize, PageReport
from .batch import process_batch


def _rich_print(report: PageReport) -> None:
    """用 Rich 库格式化输出报告."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.markdown import Markdown

        console = Console()
        md = report.to_markdown()
        console.print(Panel(md, title=f"[bold blue]{report.title or '无标题'}[/bold blue]"))
    except ImportError:
        # 降级为纯文本
        print(report.to_markdown())


def _json_output(report: PageReport) -> None:
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))


def _json_output_batch(reports: list[PageReport]) -> None:
    print(json.dumps([r.to_dict() for r in reports], ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 单 URL 命令
# ---------------------------------------------------------------------------

def cmd_single(args: argparse.Namespace) -> None:
    """处理单个 URL."""
    print(f"🌐 正在提取: {args.url}")

    if args.browser:
        import asyncio
        from .extractor import extract_browser
        page = asyncio.run(extract_browser(args.url, args.task))
    else:
        page = extract_static(args.url)

    print(f"  标题: {page.title}")
    print(f"  正文: {len(page.text)} 字符 | 链接: {len(page.links)} 个")
    print(f"🧠 正在分析...")

    report = summarize(page, args.prompt)

    if args.output == "json":
        _json_output(report)
    elif args.output == "md":
        print(report.to_markdown())
    else:
        _rich_print(report)

    # 保存文件
    if args.save:
        out_path = Path(args.save)
        if out_path.suffix == ".json":
            out_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            out_path.write_text(report.to_markdown(), encoding="utf-8")
        print(f"💾 已保存: {out_path}")


# ---------------------------------------------------------------------------
# 批量命令
# ---------------------------------------------------------------------------

def cmd_batch(args: argparse.Namespace) -> None:
    """批量处理多个 URL."""
    # 从文件读取 URL
    if args.file:
        urls = [line.strip() for line in Path(args.file).read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")]
    else:
        urls = args.urls

    if not urls:
        print("❌ 请提供 URL 列表 (--file 或直接在命令行传入)")
        sys.exit(1)

    print(f"📋 批量处理 {len(urls)} 个 URL (并发: {args.workers})")
    reports = process_batch(urls, max_workers=args.workers, custom_prompt=args.prompt)

    print(f"\n✅ 完成: {len(reports)}/{len(urls)} 个成功\n")

    if args.output == "json":
        _json_output_batch(reports)
    else:
        for report in reports:
            _rich_print(report)

    if args.save:
        out_path = Path(args.save)
        data = [r.to_dict() for r in reports]
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"💾 已保存: {out_path}")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Web Agent — 智能网页信息采集与摘要",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # 子命令: single
    single = subparsers.add_parser("fetch", help="提取单个网页",
                                   aliases=["f"])
    single.add_argument("url", help="目标网页 URL")
    single.add_argument("--browser", "-b", action="store_true",
                        help="使用浏览器模式 (JS渲染页面)")
    single.add_argument("--task", "-t", default=None,
                        help="自定义提取任务描述 (浏览器模式)")
    single.add_argument("--prompt", "-p", default=None,
                        help="自定义 LLM 分析提示词")
    single.add_argument("--output", "-o", default="rich",
                        choices=["rich", "md", "json"], help="输出格式")
    single.add_argument("--save", "-s", default=None,
                        help="保存到文件 (根据后缀自动选择格式)")

    # 子命令: batch
    batch_parser = subparsers.add_parser("batch", help="批量处理多个 URL",
                                         aliases=["b"])
    batch_parser.add_argument("urls", nargs="*", help="URL 列表 (可传入多个)")
    batch_parser.add_argument("--file", "-f", default=None,
                              help="从文件读取 URL 列表 (每行一个)")
    batch_parser.add_argument("--workers", "-w", type=int, default=3,
                              help="并发数 (默认3)")
    batch_parser.add_argument("--prompt", "-p", default=None,
                              help="自定义 LLM 分析提示词")
    batch_parser.add_argument("--output", "-o", default="rich",
                              choices=["rich", "json"], help="输出格式")
    batch_parser.add_argument("--save", "-s", default=None,
                              help="保存 JSON 结果到文件")

    args = parser.parse_args()

    if args.command in ("fetch", "f"):
        cmd_single(args)
    elif args.command in ("batch", "b"):
        cmd_batch(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
