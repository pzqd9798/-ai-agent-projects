"""LangGraph 版旅行规划助手 - 入口"""
import uvicorn
from app.api.main import app
from app.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # 改代码自动重启，不用手动 Ctrl+C
    )
