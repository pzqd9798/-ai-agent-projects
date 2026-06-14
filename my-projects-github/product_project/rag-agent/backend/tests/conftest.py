"""测试配置 — 使用临时文件数据库，每次测试前重建表."""

import os
import tempfile
from pathlib import Path

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """每次测试使用临时文件数据库，避免 in-memory 引擎不一致问题."""

    # 1. 创建临时数据库文件
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_url = f"sqlite+aiosqlite:///{tmp_db.name}"
    tmp_db.close()

    # 2. 修改配置
    os.environ["DATABASE_URL"] = db_url
    os.environ["JWT_SECRET"] = "test-secret"

    from app.config import infra
    infra.database_url = db_url
    infra.jwt_secret = "test-secret"

    # 3. 重置 database.py 全局状态
    import app.database as db_mod
    db_mod._engine = None
    db_mod._session_factory = None

    # 4. 初始化数据库
    from app.database import init_db
    await init_db()

    # 5. 重置 embedder 缓存
    from app.engine import embedder as emb_mod
    emb_mod._embedder_cache = None
    emb_mod.EMBEDDER_BACKEND = ""

    # 6. 重置 pipeline 缓存
    from app.api.chat import _pipeline_cache
    _pipeline_cache.clear()

    yield

    # 7. 清理
    _pipeline_cache.clear()
    if db_mod._engine:
        await db_mod._engine.dispose()
        db_mod._engine = None
        db_mod._session_factory = None

    # 删除临时数据库文件
    try:
        Path(tmp_db.name).unlink(missing_ok=True)
    except Exception:
        pass
