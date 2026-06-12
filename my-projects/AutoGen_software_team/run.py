#!/usr/bin/env python3
"""AutoGen 软件研发团队 — CLI 入口.

用法:
    python run.py                          # 默认任务 (比特币追踪器)
    python run.py --task todo-api          # 预设任务
    python run.py --task "你的自定义任务"   # 自定义任务
    python run.py --list                   # 列出预设任务
    python run.py --max-turns 30           # 自定义最大轮次
"""

import sys
import asyncio
import argparse
from dotenv import load_dotenv

load_dotenv()

from team.orchestrator import run_team, PRESET_TASKS


def main():
    parser = argparse.ArgumentParser(description="🤖 AutoGen 软件研发团队")
    parser.add_argument("--task", "-t", type=str, default="bitcoin-tracker",
                        help="任务名称或自定义任务描述")
    parser.add_argument("--max-turns", "-m", type=int, default=20,
                        help="最大对话轮次 (默认20)")
    parser.add_argument("--list", "-l", action="store_true",
                        help="列出所有预设任务")
    args = parser.parse_args()

    if args.list:
        print("📋 预设任务:\n")
        for name, desc in PRESET_TASKS.items():
            first_line = desc.strip().split("\n")[0]
            print(f"  {name}: {first_line}")
        return

    # 获取任务: 优先匹配预设，否则作为自定义任务
    task = PRESET_TASKS.get(args.task, args.task)

    try:
        asyncio.run(run_team(task, max_turns=args.max_turns))
    except ValueError as e:
        print(f"❌ 配置错误: {e}")
        print("请检查 .env 文件中的 LLM_API_KEY 和 LLM_MODEL_ID")
    except Exception as e:
        print(f"❌ 运行错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
