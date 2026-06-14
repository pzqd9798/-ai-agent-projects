"""Pydantic 数据模型 — API 请求/响应的强类型定义."""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ========================================================================
# 用户 & 认证
# ========================================================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=128)

class UserLogin(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class APIKeyCreate(BaseModel):
    name: str = "default"

class APIKeyResponse(BaseModel):
    id: str
    key: str
    name: str
    created_at: str
    last_used_at: Optional[str] = None


# ========================================================================
# 项目
# ========================================================================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str = Field(..., min_length=10)
    template_id: str = "full-stack"

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    template_id: str
    status: str
    created_at: str
    updated_at: str
    phase_count: int = 0


# ========================================================================
# 阶段执行
# ========================================================================

class PhaseExecuteRequest(BaseModel):
    """请求执行一个阶段."""
    phase: str = Field(..., pattern="^(plan|code|review)$")
    feedback: Optional[str] = None

class PhaseResponse(BaseModel):
    id: str
    project_id: str
    phase: str
    role: str
    input_prompt: str
    output_text: Optional[str] = None
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    tokens_used: int = 0
    error_message: Optional[str] = None


# ========================================================================
# 产物 & 版本
# ========================================================================

class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    file_path: str
    content: str
    language: str
    version: int
    created_at: str

class VersionSnapshot(BaseModel):
    id: str
    project_id: str
    version_number: int
    message: str
    created_at: str

class VersionDiff(BaseModel):
    from_version: int
    to_version: int
    files_added: List[str]
    files_removed: List[str]
    files_modified: List[str]


# ========================================================================
# Agent 模板
# ========================================================================

class AgentRoleDef(BaseModel):
    name: str
    system_prompt: str
    icon: str = "🤖"
    tools: List[str] = []

class AgentTemplateDef(BaseModel):
    name: str
    display_name: str
    description: str
    roles: List[AgentRoleDef]

class AgentTemplateResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str
    roles: List[AgentRoleDef]
    is_builtin: bool
    created_at: str


# ========================================================================
# WebSocket 事件
# ========================================================================

class WSEvent(BaseModel):
    type: str          # "phase_start" | "agent_message" | "phase_complete" | "error"
    project_id: str
    phase: Optional[str] = None
    role: Optional[str] = None
    content: Optional[str] = None
    metadata: dict = {}


# ========================================================================
# 统计
# ========================================================================

class DashboardStats(BaseModel):
    total_projects: int
    total_users: int
    total_phases_executed: int
    total_tokens_used: int
    projects_by_status: dict
    recent_projects: List[ProjectResponse]
