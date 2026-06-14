"""Pydantic 模型 — 请求/响应验证."""

from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    user_id: int


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    api_key: str | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

class KBCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = []


class KBUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    tags: list[str] | None = None


class KBResponse(BaseModel):
    id: int
    name: str
    description: str
    tags: list[str]
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

class DocumentResponse(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}

    id: int
    filename: str
    format: str
    file_size: int
    status: str
    chunk_count: int = 0
    metadata_: dict = Field(default_factory=dict, alias="metadata")
    created_at: datetime


class DocumentUploadResponse(BaseModel):
    id: int
    filename: str
    status: str
    message: str = ""


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    kb_id: int | None = None       # 指定知识库，不指定则用最近
    session_id: int | None = None  # 指定会话，不指定则新建
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = False


class SourceInfo(BaseModel):
    filename: str
    chunk_index: int
    score: float
    snippet: str = ""


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceInfo] = []
    retrieved_count: int = 0
    elapsed_ms: float = 0
    session_id: int


class ChatSessionResponse(BaseModel):
    id: int
    title: str
    kb_id: int | None = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: list[SourceInfo] = []
    elapsed_ms: float = 0
    created_at: datetime


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    kb_id: int | None = None
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    chunk_id: str
    text: str
    source: str
    score: float
    metadata_: dict = Field(default_factory=dict, alias="metadata")


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------

class UserMemoryResponse(BaseModel):
    preferences: dict[str, str]
    facts: list[str]
    session_summaries: list[str]


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class StatsResponse(BaseModel):
    total_users: int = 0
    total_knowledge_bases: int = 0
    total_documents: int = 0
    total_chunks: int = 0
    total_chat_sessions: int = 0
    total_messages: int = 0
    uptime_seconds: float = 0
