"""FastAPI entry point — production-grade deep research platform.

Layers integrated:
  1. Auth: JWT + API Key dual authentication
  2. Database: SQLAlchemy async with 7 tables
  3. Rate limiting: per-IP sliding window
  4. CORS: configurable origins
  5. Observability: structured logging + metrics endpoint
  6. SSE streaming: real-time research progress
  7. Security: prompt injection detection
"""

from __future__ import annotations

import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

# Load .env early
load_dotenv()

from config import Configuration, SearchAPI
from database import check_db_health, init_db
from models.schemas import HealthResponse
from security.input_guard import sanitize_input
from security.rate_limit import get_rate_limiter
from services.observability import get_logger, get_metrics

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logger.remove()
logger.add(
    sys.stderr,
    level=log_level,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | "
    "<cyan>{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)

_obs_logger = get_logger()
_metrics = get_metrics()


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Startup
    logger.info("Starting Deep Research Platform...")

    # Init database
    try:
        await init_db()
        db_ok = await check_db_health()
        logger.info("Database: %s", "connected" if db_ok else "unavailable")
    except Exception as exc:
        logger.warning("Database init failed (non-fatal): %s", exc)

    # Log config
    config = Configuration.from_env()
    logger.info(
        "Provider: %s | Model: %s | Search: %s | Max loops: %s",
        config.llm_provider,
        config.resolved_model() or "unset",
        config.search_api.value if hasattr(config.search_api, "value") else config.search_api,
        config.max_web_research_loops,
    )

    yield

    # Shutdown
    logger.info("Deep Research Platform shutting down")
    from database import _engine
    if _engine:
        await _engine.dispose()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Deep Research Platform",
        description="Production-grade multi-agent deep research with LangGraph orchestration",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS
    cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # Rate limiting middleware
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        limiter = get_rate_limiter()

        if not limiter.allow(client_ip):
            _metrics.incr("rate_limited")
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
            )

        response = await call_next(request)
        return response

    # Request ID middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        import uuid
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "name": "Deep Research Platform",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
            "metrics": "/metrics",
        }

    @app.get("/health", response_model=HealthResponse)
    async def health_check():
        db_status = "ok" if await check_db_health() else "error"
        config = Configuration.from_env()
        return HealthResponse(
            status="healthy" if db_status == "ok" else "degraded",
            database=db_status,
            llm_provider=config.llm_provider,
            search_backend=(
                config.search_api.value
                if hasattr(config.search_api, "value")
                else str(config.search_api)
            ),
        )

    @app.get("/metrics")
    async def metrics_endpoint():
        """Prometheus-compatible metrics export."""
        return JSONResponse(content=_metrics.get_snapshot())

    # Register API routers
    from api.auth import router as auth_router
    from api.research import router as research_router
    from api.ws import router as ws_router

    app.include_router(auth_router)
    app.include_router(research_router)
    app.include_router(ws_router)

    # ------------------------------------------------------------------
    # Legacy compatibility endpoints (forward to new API)
    # ------------------------------------------------------------------

    @app.post("/research")
    async def legacy_research(payload: dict[str, Any]):
        """Legacy endpoint — forwards to /api/research."""
        from models.schemas import ResearchRequest
        req = ResearchRequest(
            topic=payload.get("topic", ""),
            search_api=payload.get("search_api"),
        )
        # Import here to avoid circular
        from api.research import start_research
        from api.auth import get_current_user
        logger.warning("Legacy /research endpoint used; migrate to /api/research")
        raise HTTPException(status_code=410, detail="请使用 /api/research 端点")

    @app.post("/research/stream")
    async def legacy_stream(payload: dict[str, Any]):
        """Legacy streaming endpoint — forwards to /ws/research/stream."""
        logger.warning("Legacy /research/stream endpoint used; migrate to /ws/research/stream")
        raise HTTPException(status_code=410, detail="请使用 /ws/research/stream 端点")

    @app.get("/healthz")
    async def legacy_health():
        return {"status": "ok", "note": "use /health instead"}

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


app = create_app()

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level=log_level.lower(),
    )
