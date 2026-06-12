"""求职助手 — 自动搜索职位、提取JD、匹配简历、生成报告.

用法:
    # 演示模式 (不需要额外依赖)
    python -m job_agent demo

    # 真实搜索 + LLM 匹配
    python -m job_agent search "Python后端" -l "北京"

    # 保存报告
    python -m job_agent search "AI工程师" -o json -s report.json
    python -m job_agent demo -s report.md

    # Python API
    from job_agent.demo import demo_match_batch
    report = demo_match_batch()
"""

from .cli import main

if __name__ == "__main__":
    main()
