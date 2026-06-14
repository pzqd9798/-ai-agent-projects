"""SQLite 异步数据库访问 — 8 张表，完整知识库产品架构."""

import re
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Float, DateTime, ForeignKey, JSON, Boolean,
)
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import infra


# ---------------------------------------------------------------------------
# 引擎与会话
# ---------------------------------------------------------------------------

_engine = None
_session_factory: async_sessionmaker | None = None


def _get_url() -> str:
    url = infra.database_url
    return re.sub(r"^sqlite://", "sqlite+aiosqlite://", url)


async def get_db() -> AsyncSession:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            create_async_engine(_get_url(), echo=False),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    async with _session_factory() as session:
        yield session


async def init_db():
    """创建所有表."""
    global _engine
    _engine = create_async_engine(_get_url(), echo=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return _engine


# ---------------------------------------------------------------------------
# ORM 基类
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 表定义
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(128), nullable=False)
    api_key = Column(String(64), unique=True, nullable=True)
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    knowledge_bases = relationship("KnowledgeBase", back_populates="owner")
    sessions = relationship("ChatSession", back_populates="user")


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text, default="")
    tags = Column(JSON, default=list)       # ["技术", "Python"]
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="knowledge_bases")
    documents = relationship("Document", back_populates="knowledge_base", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False)
    filename = Column(String(300), nullable=False)
    format = Column(String(20), nullable=False)   # pdf, txt, md
    file_size = Column(Integer, default=0)
    status = Column(String(20), default="pending")  # pending, processing, ready, error
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(32), primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    text = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)
    metadata_ = Column("metadata", JSON, default=dict)
    embedding = Column(JSON, nullable=True)          # JSON-serialized float list

    document = relationship("Document", back_populates="chunks")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True)
    title = Column(String(200), default="New Chat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)        # user, assistant
    content = Column(Text, nullable=False)
    sources = Column(JSON, default=list)             # 引用来源
    elapsed_ms = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


class UserMemory(Base):
    __tablename__ = "user_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    memory_type = Column(String(30), nullable=False)  # preference, fact, session_summary
    key = Column(String(200), default="")
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    kb_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=True)
    action = Column(String(50), nullable=False)       # chat, ingest, search
    tokens_used = Column(Integer, default=0)
    elapsed_ms = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
