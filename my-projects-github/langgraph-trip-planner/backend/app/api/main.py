"""FastAPI 主应用 - LangGraph 版旅行规划助手"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..config import get_settings, validate_config, print_config
from .routes import trip, poi, map as map_routes

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基于 LangGraph StateGraph 的智能旅行规划助手 —— 并行搜索 + 条件重试 + Checkpoint",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(trip.router, prefix="/api")
app.include_router(poi.router, prefix="/api")
app.include_router(map_routes.router, prefix="/api")


@app.on_event("startup")
async def startup():
    print("\n" + "=" * 60)
    print(f"🚀 {settings.app_name} v{settings.app_version}")
    print("   🧠 引擎: LangGraph StateGraph")
    print("   ⚡ 特性: 并行搜索 | 条件重试 | Checkpoint")
    print("=" * 60)
    print_config()
    try:
        validate_config()
        print("✅ 配置验证通过")
    except ValueError as e:
        print(f"❌ 配置验证失败:\n{e}")
        raise
    print(f"\n📚 API 文档: http://localhost:{settings.port}/docs")
    print(f"📖 ReDoc: http://localhost:{settings.port}/redoc")
    print("=" * 60 + "\n")


@app.on_event("shutdown")
async def shutdown():
    print("\n👋 LangGraph 旅行助手已关闭\n")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "engine": "LangGraph StateGraph",
        "features": ["parallel_search", "conditional_retry", "checkpoint"],
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "engine": "LangGraph",
        "version": settings.app_version,
    }
