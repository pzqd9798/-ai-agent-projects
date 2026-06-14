"""JWT + API Key dual authentication for the deep research platform."""

from __future__ import annotations

import datetime
import hashlib
import os
import secrets
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models.db_models import User
from models.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserMeResponse,
    UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])

# ---------------------------------------------------------------------------
# Crypto setup
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer_scheme = HTTPBearer(auto_error=False)
JWT_SECRET = os.getenv("JWT_SECRET", secrets.token_urlsafe(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "168"))  # 1 week


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def create_jwt(user_id: int, username: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.datetime.now(datetime.timezone.utc),
        "exp": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效的 Token")


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate via Bearer JWT or X-API-Key header. Returns User."""

    user = None

    # 1. Try Bearer token
    if credentials:
        payload = decode_jwt(credentials.credentials)
        result = await db.execute(
            select(User).where(User.id == int(payload["sub"]))
        )
        user = result.scalar_one_or_none()

    # 2. Try API Key
    if user is None:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            result = await db.execute(
                select(User).where(User.api_key == api_key)
            )
            user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="未认证 — 请提供 Bearer Token 或 X-API-Key")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已禁用")

    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user. Returns JWT token."""
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    if req.email:
        result = await db.execute(
            select(User).where(User.email == req.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="邮箱已被注册")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        api_key=f"dr-{secrets.token_urlsafe(24)}",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_jwt(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            api_key=user.api_key,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username + password. Returns JWT."""
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已禁用")

    token = create_jwt(user.id, user.username)
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            api_key=user.api_key,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserMeResponse)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile with usage stats."""
    from sqlalchemy import func

    from models.db_models import ResearchSession

    session_count_result = await db.execute(
        select(func.count(ResearchSession.id)).where(
            ResearchSession.user_id == user.id
        )
    )
    session_count = session_count_result.scalar() or 0

    return UserMeResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        api_key=user.api_key,
        is_active=user.is_active,
        created_at=user.created_at,
        session_count=session_count,
        total_research_hours=0.0,
    )
