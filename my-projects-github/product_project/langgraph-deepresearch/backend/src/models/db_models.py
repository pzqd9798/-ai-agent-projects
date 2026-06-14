"""SQLAlchemy ORM models — 7 tables for the deep research platform."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relations
    research_sessions: Mapped[list["ResearchSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    usage_logs: Mapped[list["UsageLog"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Research Sessions
# ---------------------------------------------------------------------------


class ResearchSession(Base):
    __tablename__ = "research_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(String(512), nullable=False)
    search_api: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending, running, completed, failed
    todo_items_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_markdown: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_note_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    elapsed_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relations
    user: Mapped["User"] = relationship(back_populates="research_sessions")
    messages: Mapped[list["ResearchMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    search_results: Mapped[list["SearchResult"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Research Messages (SSE events log)
# ---------------------------------------------------------------------------


class ResearchMessage(Base):
    __tablename__ = "research_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("research_sessions.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    session: Mapped["ResearchSession"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Search Results (cache)
# ---------------------------------------------------------------------------


class SearchResult(Base):
    __tablename__ = "search_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("research_sessions.id"), nullable=False, index=True
    )
    query: Mapped[str] = mapped_column(String(1024), nullable=False)
    backend: Mapped[str] = mapped_column(String(32), nullable=False)
    results_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notices_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    session: Mapped["ResearchSession"] = relationship(back_populates="search_results")


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    note_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("research_sessions.id"), nullable=True, index=True
    )
    task_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(256), default="Untitled")
    note_type: Mapped[str] = mapped_column(String(32), default="general")
    tags_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="notes")


# ---------------------------------------------------------------------------
# Source Cache (cross-session page content cache)
# ---------------------------------------------------------------------------


class SourceCache(Base):
    __tablename__ = "source_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    ttl_seconds: Mapped[int] = mapped_column(Integer, default=86400)  # 24 h


# ---------------------------------------------------------------------------
# Usage Logs
# ---------------------------------------------------------------------------


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("research_sessions.id"), nullable=True
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="usage_logs")
