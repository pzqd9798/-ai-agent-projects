# Agent Harness Demo
# 可调试的 Agent 循环 — Agent = Model + Harness
#
# 用法:
#     python run.py
#     python run.py --debug
#     python run.py --trace
#
# 架构:
#     run.py → core.py (Agent 循环)
#               ├── tools.py   (工具定义 + 分发表)
#               ├── logger.py  (5 级调试日志)
#               └── session.py (会话录制 + 统计)
