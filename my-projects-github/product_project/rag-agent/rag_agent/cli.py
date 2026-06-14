"""CLI — RAG 知识助手命令行接口."""

import sys
import argparse
from pathlib import Path

from .agent import RAGAgent


def cmd_ingest(args):
    agent = RAGAgent()
    if args.dir:
        n = agent.ingest_directory(args.dir)
        print(f"已索引目录 {args.dir}: {n} 个片段")
    else:
        for path in args.files:
            n = agent.ingest_file(path)
            print(f"已索引 {path}: {n} 个片段")
    print(f"统计: {agent.stats()}")


def cmd_query(args):
    agent = RAGAgent()

    # 恢复记忆
    if args.load:
        agent.load_memory(args.load)

    print("📚 RAG 知识助手 (输入 quit 退出)")
    print(f"   模型: {agent.model} | 片段: {agent.stats()['total_chunks']}")
    print()

    while True:
        try:
            q = input("❓ > ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not q:
            continue
        if q.lower() in ("quit", "exit"):
            break

        response = agent.query(q)
        print(f"\n{response.answer}\n")
        if response.sources:
            print(f"📖 来源: {', '.join(response.sources)}")
            print(f"⏱ {response.elapsed_ms:.0f}ms")
        print()

    # 保存记忆
    if args.save:
        agent.save_memory(args.save)
        print(f"记忆已保存: {args.save}")


def main():
    parser = argparse.ArgumentParser(description="RAG 知识助手")
    sub = parser.add_subparsers(dest="cmd")

    # ingest
    ingest = sub.add_parser("ingest", help="索引文档")
    ingest.add_argument("files", nargs="*", help="文档路径")
    ingest.add_argument("--dir", "-d", help="目录路径 (批量)")

    # query
    query = sub.add_parser("query", help="交互式问答")
    query.add_argument("--load", "-l", help="加载长期记忆文件")
    query.add_argument("--save", "-s", help="保存长期记忆文件")

    args = parser.parse_args()

    if args.cmd == "ingest":
        cmd_ingest(args)
    elif args.cmd == "query":
        cmd_query(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
