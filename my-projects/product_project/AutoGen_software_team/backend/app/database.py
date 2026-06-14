"""数据库层 — SQLite 异步访问, 管理项目/用户/版本/模板."""

import aiosqlite
import uuid
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import config

DB_PATH = config.database.path

# ---------------------------------------------------------------------------
# 连接管理
# ---------------------------------------------------------------------------

async def get_db() -> aiosqlite.Connection:
    """获取数据库连接 (启动时调用 init_db 后)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(DB_PATH))
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db():
    """初始化数据库表结构."""
    conn = await get_db()
    try:
        await conn.executescript("""
            -- 用户表
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- API 密钥
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                key TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT 'default',
                created_at TEXT DEFAULT (datetime('now')),
                last_used_at TEXT
            );

            -- 项目表
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id),
                name TEXT NOT NULL,
                description TEXT,
                template_id TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            -- 阶段执行记录
            CREATE TABLE IF NOT EXISTS phases (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                phase TEXT NOT NULL,
                role TEXT NOT NULL,
                input_prompt TEXT,
                output_text TEXT,
                status TEXT DEFAULT 'pending',
                started_at TEXT,
                finished_at TEXT,
                tokens_used INTEGER DEFAULT 0,
                error_message TEXT
            );

            -- 生成产物 (代码文件)
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                phase_id TEXT REFERENCES phases(id),
                file_path TEXT NOT NULL,
                content TEXT,
                language TEXT,
                version INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- 版本快照
            CREATE TABLE IF NOT EXISTS versions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id),
                version_number INTEGER NOT NULL,
                message TEXT,
                snapshot_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- Agent 模板
            CREATE TABLE IF NOT EXISTS agent_templates (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                roles_json TEXT NOT NULL,
                is_builtin INTEGER DEFAULT 0,
                created_by TEXT REFERENCES users(id),
                created_at TEXT DEFAULT (datetime('now'))
            );

            -- 审计日志
            CREATE TABLE IF NOT EXISTS audit_log (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                project_id TEXT,
                action TEXT NOT NULL,
                detail TEXT,
                ip_address TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await conn.commit()

        # 确保默认管理员存在
        await _ensure_default_admin(conn)
        # 导入内置模板
        await _ensure_builtin_templates(conn)
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# 种子数据
# ---------------------------------------------------------------------------

async def _ensure_default_admin(conn: aiosqlite.Connection):
    """创建默认管理员账号 (admin / admin123)."""
    import hashlib
    row = await conn.execute_fetchall("SELECT id FROM users WHERE username='admin'")
    if not row:
        uid = str(uuid.uuid4())
        pw = hashlib.sha256("admin123".encode()).hexdigest()
        await conn.execute(
            "INSERT INTO users(id, username, password_hash, role) VALUES(?,?,?,?)",
            (uid, "admin", pw, "admin"),
        )
        # 生成默认 API Key
        api_key = "ak-" + str(uuid.uuid4()).replace("-", "")[:24]
        await conn.execute(
            "INSERT INTO api_keys(id, user_id, key, name) VALUES(?,?,?,?)",
            (str(uuid.uuid4()), uid, api_key, "default"),
        )
        print(f"[DB] 默认管理员已创建: admin / admin123")
        print(f"[DB] Admin API Key: {api_key}")
        await conn.commit()


async def _ensure_builtin_templates(conn: aiosqlite.Connection):
    """导入内置 Agent 模板."""
    from app.engine.templates import BUILTIN_TEMPLATES
    for tmpl in BUILTIN_TEMPLATES:
        row = await conn.execute_fetchall(
            "SELECT id FROM agent_templates WHERE name=?", (tmpl["name"],)
        )
        if not row:
            await conn.execute(
                """INSERT INTO agent_templates(id, name, display_name, description, roles_json, is_builtin)
                   VALUES(?,?,?,?,?,1)""",
                (
                    str(uuid.uuid4()),
                    tmpl["name"],
                    tmpl["display_name"],
                    tmpl["description"],
                    json.dumps(tmpl["roles"], ensure_ascii=False),
                ),
            )
    await conn.commit()


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_id() -> str:
    return str(uuid.uuid4())
