"""SQLAlchemy async ORM — 7 tables for multi-tenant deep research persistence."""

from __future__ import annotations

import os
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# ---------------------------------------------------------------------------
# Engine & session factory (lazy init so tests can override)
# ---------------------------------------------------------------------------

_engine = None
_session_factory = None


def _get_url() -> str:
    url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/deepresearch.db")
    if url.startswith("sqlite:///"):
        url = url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    elif url.startswith("sqlite://"):
        url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def _get_engine():
    global _engine
    if _engine is None:
        db_url = _get_url()
        if "aiosqlite" in db_url:
            db_path = db_url.split("sqlite+aiosqlite:///", 1)[-1]
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(db_url, echo=False, future=True)
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async DB session."""
    factory = _get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_health() -> bool:
    """Return True if the database is reachable."""
    try:
        factory = _get_session_factory()
        async with factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
