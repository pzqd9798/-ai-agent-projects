"""认证 API — JWT + API Key 双认证."""

import uuid
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import infra
from app.database import User, get_db
from app.models.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT 工具
# ---------------------------------------------------------------------------

def create_access_token(user_id: int, username: str) -> str:
    expire = datetime.utcnow() + timedelta(minutes=infra.jwt_expire_minutes)
    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expire,
    }
    return jwt.encode(payload, infra.jwt_secret, algorithm=infra.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, infra.jwt_secret, algorithms=[infra.jwt_algorithm])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# 依赖注入 — 获取当前用户
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """从 JWT Bearer 或 X-API-Key 中解析用户."""
    user = None

    # 方式 1: JWT Bearer
    if credentials:
        payload = decode_token(credentials.credentials)
        if payload:
            user_id = int(payload.get("sub", 0))
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

    # 方式 2: API Key
    if user is None and x_api_key:
        result = await db.execute(select(User).where(User.api_key == x_api_key))
        user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=401, detail="未认证或凭据无效")

    return user


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户，返回 JWT Token 和 API Key."""
    # 检查用户名是否已存在
    existing = await db.execute(
        select(User).where(User.username == req.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名已存在")

    # 创建用户
    user = User(
        username=req.username,
        password_hash=pwd_context.hash(req.password),
        api_key=f"rag-{secrets.token_hex(24)}",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.username)

    return TokenResponse(
        access_token=token,
        username=user.username,
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录."""
    result = await db.execute(
        select(User).where(User.username == req.username)
    )
    user = result.scalar_one_or_none()

    if not user or not pwd_context.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.id, user.username)

    return TokenResponse(
        access_token=token,
        username=user.username,
        user_id=user.id,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息."""
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        api_key=user.api_key,
        created_at=user.created_at,
    )


@router.post("/api-key/rotate")
async def rotate_api_key(user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """轮换 API Key."""
    user.api_key = f"rag-{secrets.token_hex(24)}"
    db.add(user)
    await db.commit()
    return {"api_key": user.api_key, "message": "API Key 已更新"}
