"""Test infrastructure — temp database, fixture isolation, global state reset."""

import os
import secrets
import tempfile
from pathlib import Path

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Each test gets a fresh temp database, isolated from production."""

    # 1. Create temp database file
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_url = f"sqlite+aiosqlite:///{tmp_db.name}"
    tmp_db.close()

    # 2. Override config for testing
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = secrets.token_urlsafe(32)
    os.environ["LLM_API_KEY"] = ""  # No real LLM calls in tests
    os.environ["SEARCH_API"] = "duckduckgo"
    os.environ["LOG_LEVEL"] = "ERROR"

    # 3. Reset database globals
    import database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    # 4. Init test database
    from database import init_db
    await init_db()

    yield db_url

    # 5. Cleanup
    if db_mod._engine:
        await db_mod._engine.dispose()
        db_mod._engine = None
        db_mod._session_factory = None

    try:
        Path(tmp_db.name).unlink(missing_ok=True)
    except Exception:
        pass
