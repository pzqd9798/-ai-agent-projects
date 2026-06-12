# Agent Harness Demo
# A debuggable agent loop — Agent = Model + Harness
#
# Usage:
#     python run.py
#     python run.py --debug
#     python run.py --trace
#
# Architecture:
#     run.py → core.py (agent loop)
#               ├── tools.py   (tool definitions + dispatch map)
#               ├── logger.py  (5-level debug logging)
#               └── session.py (session recording + stats)
