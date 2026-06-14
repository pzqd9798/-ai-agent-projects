#!/usr/bin/env python3
"""Coding Agent Pro — 一键启动脚本.

用法:
    python start.py                # 仅启动 FastAPI 后端
    python start.py --full         # 启动后端 + Frontend
    python start.py --worker       # 启动 arq Worker

环境变量:
    LLM_API_KEY      LLM API 密钥 (必填)
    LLM_MODEL_ID     模型 ID (默认 deepseek-chat)
    LLM_BASE_URL     API 地址 (默认 https://api.deepseek.com)
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "backend"))


def check_env():
    """检查必要的环境变量."""
    issues = []
    if not os.getenv("LLM_API_KEY"):
        # 尝试从 .env 加载
        env_file = ROOT_DIR / ".env"
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
        if not os.getenv("LLM_API_KEY"):
            issues.append("LLM_API_KEY 未设置, Agent 调用将失败")

    if issues:
        print("⚠️  警告:")
        for i in issues:
            print(f"  - {i}")
        print()

    # 检查 Python 依赖
    try:
        import fastapi
        import autogen_agentchat
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("   运行: pip install -r backend/requirements.txt")
        sys.exit(1)

    return True


def start_api():
    """启动 FastAPI 后端."""
    import uvicorn
    from app.config import config

    print(f"""
╔══════════════════════════════════════════════════════════╗
║          🤖 Coding Agent Pro  v{config.app.version}              ║
║          AutoGen Multi-Agent Software Team               ║
╚══════════════════════════════════════════════════════════╝

  API 文档:    http://localhost:{config.app.port}/docs
  健康检查:    http://localhost:{config.app.port}/health
  产品首页:    http://localhost:{config.app.port}/

  Streamlit:   streamlit run frontend/app.py

  按 Ctrl+C 停止服务
{'─' * 60}
""")

    uvicorn.run(
        "app.main:app",
        host=config.app.host,
        port=config.app.port,
        reload=config.app.debug,
        log_level="info",
    )


def start_worker():
    """启动 arq Worker."""
    print("🚀 启动 arq Worker...")
    subprocess.run([
        "arq", "app.worker.tasks.WorkerSettings",
    ], cwd=ROOT_DIR / "backend")


def start_frontend():
    """启动 Streamlit 前端."""
    print("🎨 启动 Streamlit 前端...")
    subprocess.run([
        "streamlit", "run", "frontend/app.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0",
    ], cwd=ROOT_DIR)


def main():
    parser = argparse.ArgumentParser(description="Coding Agent Pro 启动器")
    parser.add_argument("--full", action="store_true", help="启动所有服务")
    parser.add_argument("--worker", action="store_true", help="仅启动 Worker")
    parser.add_argument("--frontend", action="store_true", help="仅启动前端")
    args = parser.parse_args()

    check_env()

    if args.worker:
        start_worker()
    elif args.frontend:
        start_frontend()
    elif args.full:
        # 多进程启动
        import threading
        api_thread = threading.Thread(target=start_api, daemon=True)
        frontend_thread = threading.Thread(target=start_frontend, daemon=True)

        api_thread.start()
        print("⏳ 等待 API 就绪...")
        import time
        time.sleep(2)
        frontend_thread.start()

        print("\n✅ 全部服务已启动")
        print("   API:       http://localhost:8000")
        print("   Frontend:  http://localhost:8501")
        print("\n   按 Ctrl+C 停止\n")

        try:
            api_thread.join()
            frontend_thread.join()
        except KeyboardInterrupt:
            print("\n🛑 服务已停止")
    else:
        start_api()


if __name__ == "__main__":
    main()
