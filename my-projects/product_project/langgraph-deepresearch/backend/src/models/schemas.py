"""Pydantic schemas for API requests and responses."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    email: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    api_key: str
    is_active: bool = True
    created_at: datetime.datetime | str | None = None

    model_config = {"from_attributes": True}


class UserMeResponse(UserResponse):
    """Extended user info with usage stats."""
    session_count: int = 0
    total_research_hours: float = 0.0


# ---------------------------------------------------------------------------
# Research
# ---------------------------------------------------------------------------


class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=1024, description="Research topic")
    search_api: str | None = Field(
        default=None,
        description="Override search backend: tavily, duckduckgo, searxng, perplexity, advanced",
    )
    max_loops: int | None = Field(
        default=None, ge=1, le=10, description="Override max research iterations"
    )


class ResearchResponse(BaseModel):
    session_id: int
    topic: str
    report_markdown: str = ""
    todo_items: list[dict[str, Any]] = []
    elapsed_ms: int | None = None


class TodoItemResponse(BaseModel):
    id: int
    title: str
    intent: str
    query: str
    status: str
    summary: str | None = None
    sources_summary: str | None = None
    note_id: str | None = None
    note_path: str | None = None


class SessionResponse(BaseModel):
    id: int
    topic: str
    status: str
    search_api: str | None = None
    report_markdown: str | None = None
    todo_count: int = 0
    elapsed_ms: int | None = None
    created_at: datetime.datetime | str | None = None
    updated_at: datetime.datetime | str | None = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1024)
    session_id: int | None = None
    search_api: str | None = None
    max_results: int = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    score: float | None = None
    backend: str | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    backend: str
    answer: str | None = None
    total: int
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------


class NoteCreate(BaseModel):
    title: str = Field(default="Untitled", max_length=256)
    note_type: str = Field(default="general", max_length=32)
    tags: list[str] = []
    content: str = ""


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class NoteResponse(BaseModel):
    id: int
    note_uid: str
    title: str
    note_type: str
    tags: list[str] = []
    content: str = ""
    session_id: int | None = None
    task_id: int | None = None
    created_at: datetime.datetime | str | None = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str = "1.0.0"
    database: str = "ok"
    llm_provider: str = "unknown"
    search_backend: str = "unknown"


# Forward references
TokenResponse.model_rebuild()
