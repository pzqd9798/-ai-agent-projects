"""SQLite 数据库 — 用户、Agent配置、API Key、审计日志."""

import sqlite3
import uuid
import json
import time
from pathlib import Path
from dataclasses import dataclass, field


DB_PATH = Path(__file__).resolve().parent.parent.parent / "workspace" / "clawbot.db"


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );

        CREATE TABLE IF NOT EXISTS api_keys (
            key TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            last_used REAL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            template TEXT DEFAULT 'custom',
            system_prompt TEXT DEFAULT '',
            tools TEXT DEFAULT '[]',
            model TEXT DEFAULT 'claude-sonnet-4-6',
            status TEXT DEFAULT 'active',
            created_at REAL DEFAULT (strftime('%s', 'now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            agent_id TEXT,
            action TEXT NOT NULL,
            detail TEXT DEFAULT '',
            created_at REAL DEFAULT (strftime('%s', 'now'))
        );
    """)
    conn.commit()

    # 默认管理员
    import hashlib
    existing = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    if not existing:
        admin_id = uuid.uuid4().hex[:12]
        pw = hashlib.sha256("admin123".encode()).hexdigest()
        conn.execute("INSERT INTO users (id, username, password_hash, role) VALUES (?,?,?,?)",
                     (admin_id, "admin", pw, "admin"))
        conn.execute("INSERT INTO api_keys (key, user_id, name) VALUES (?,?,?)",
                     ("clawbot-admin-" + uuid.uuid4().hex[:8], admin_id, "Default Admin Key"))
        conn.commit()

    conn.close()


# ---------------------------------------------------------------------------
# 预置 Agent 模板
# ---------------------------------------------------------------------------

AGENT_TEMPLATES = {
    "code-assistant": {
        "name": "代码助手",
        "description": "专业的编程助手，支持代码审查、调试、重构、文件操作和 Shell 命令执行",
        "icon": "💻",
        "system_prompt": """你是一个专业的编程助手。你有以下能力：
- 读写文件、执行 Shell 命令
- 代码审查：分析代码质量、安全性、性能
- 调试：定位 bug 并给出修复方案
- 重构：优化代码结构和可读性
- 回答编程相关问题

规则：
- 修改代码前先读取文件
- 优先使用工具获取实时信息
- 给出可运行的完整代码示例
- 用中文回复""",
        "tools": ["bash", "read_file", "write_file", "web_fetch"],
        "model": "claude-sonnet-4-6",
    },
    "customer-service": {
        "name": "智能客服",
        "description": "企业级智能客服，支持知识库检索、多轮对话、情感识别",
        "icon": "🎧",
        "system_prompt": """你是一个专业的企业智能客服。你的职责：
- 耐心回答用户问题，提供准确信息
- 识别用户情绪，遇到不满时优先安抚
- 无法回答的问题如实说明，引导用户转人工
- 从知识库中检索相关信息辅助回答
- 记录用户反馈和常见问题

回复原则：
- 热情友好，使用礼貌用语
- 结构化呈现信息（列表、步骤）
- 涉及退款/投诉等敏感话题时谨慎处理
- 用中文回复""",
        "tools": ["web_fetch"],
        "model": "claude-sonnet-4-6",
    },
    "doc-qa": {
        "name": "文档问答",
        "description": "基于上传文档的智能问答助手，RAG 检索增强生成",
        "icon": "📚",
        "system_prompt": """你是一个文档问答助手。你可以：
- 读取和分析用户上传的文档（PDF、Markdown、TXT）
- 基于文档内容回答问题
- 引用原文具体段落作为依据
- 对比多个文档找出异同

规则：
- 回答必须基于文档内容，不要编造
- 引用来源时指明文件名和段落
- 如果文档中没有相关信息，如实说明
- 用中文回复""",
        "tools": ["read_file", "web_fetch"],
        "model": "claude-sonnet-4-6",
    },
}
