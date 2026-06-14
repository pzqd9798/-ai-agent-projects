"""认证 API — JWT 签发/验证/刷新 + API Key 管理."""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import config
from app.database import get_db, now_iso, new_id
from app.models import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    APIKeyCreate, APIKeyResponse,
)

router = APIRouter(prefix="/api/auth", tags=["认证"])
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# JWT 工具
# ---------------------------------------------------------------------------

def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _create_token(user_id: str, username: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=config.auth.token_expire_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, config.auth.jwt_secret, algorithm=config.auth.jwt_algorithm)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.auth.jwt_secret, algorithms=[config.auth.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token 已过期, 请重新登录")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "无效的 Token")


# ---------------------------------------------------------------------------
# 依赖注入: 获取当前用户
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    x_api_key: str = Header(None),
):
    """从 JWT 或 API Key 中解析当前用户."""
    # 优先使用 API Key
    if x_api_key:
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                """SELECT u.id, u.username, u.role
                   FROM api_keys k JOIN users u ON k.user_id = u.id
                   WHERE k.key = ?""", (x_api_key,)
            )
            if row:
                r = row[0]
                await db.execute(
                    "UPDATE api_keys SET last_used_at=? WHERE key=?",
                    (now_iso(), x_api_key),
                )
                await db.commit()
                return {"id": r[0], "username": r[1], "role": r[2]}
        finally:
            await db.close()
        raise HTTPException(401, "无效的 API Key")

    # Token 认证
    if credentials:
        payload = _decode_token(credentials.credentials)
        return {"id": payload["sub"], "username": payload["username"], "role": payload["role"]}

    raise HTTPException(401, "请提供 Bearer Token 或 X-API-Key")


async def get_admin_user(user=Depends(get_current_user)):
    """要求管理员角色."""
    if user["role"] != "admin":
        raise HTTPException(403, "需要管理员权限")
    return user


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------

@router.post("/register", response_model=TokenResponse)
async def register(data: UserCreate):
    """注册新用户."""
    db = await get_db()
    try:
        # 检查用户名
        row = await db.execute_fetchall(
            "SELECT id FROM users WHERE username=?", (data.username,)
        )
        if row:
            raise HTTPException(400, "用户名已存在")

        user_id = new_id()
        await db.execute(
            "INSERT INTO users(id, username, password_hash) VALUES(?,?,?)",
            (user_id, data.username, _hash_password(data.password)),
        )

        # 自动生成 API Key
        api_key = "ak-" + str(uuid.uuid4()).replace("-", "")[:24]
        await db.execute(
            "INSERT INTO api_keys(id, user_id, key) VALUES(?,?,?)",
            (new_id(), user_id, api_key),
        )
        await db.commit()

        token = _create_token(user_id, data.username, "user")
        return TokenResponse(
            access_token=token,
            user=UserResponse(id=user_id, username=data.username, role="user",
                            created_at=now_iso()),
        )
    finally:
        await db.close()


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    """用户登录."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT id, username, password_hash, role, created_at FROM users WHERE username=?",
            (data.username,)
        )
        if not row:
            raise HTTPException(401, "用户名或密码错误")

        r = row[0]
        if r[2] != _hash_password(data.password):
            raise HTTPException(401, "用户名或密码错误")

        token = _create_token(r[0], r[1], r[3])
        return TokenResponse(
            access_token=token,
            user=UserResponse(id=r[0], username=r[1], role=r[3], created_at=r[4]),
        )
    finally:
        await db.close()


@router.get("/me", response_model=UserResponse)
async def get_me(user=Depends(get_current_user)):
    """获取当前用户信息."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT id, username, role, created_at FROM users WHERE id=?",
            (user["id"],)
        )
        r = row[0]
        return UserResponse(id=r[0], username=r[1], role=r[2], created_at=r[3])
    finally:
        await db.close()


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(data: APIKeyCreate, user=Depends(get_current_user)):
    """为当前用户创建新的 API Key."""
    db = await get_db()
    try:
        key_id = new_id()
        api_key = "ak-" + str(uuid.uuid4()).replace("-", "")[:24]
        await db.execute(
            "INSERT INTO api_keys(id, user_id, key, name) VALUES(?,?,?,?)",
            (key_id, user["id"], api_key, data.name),
        )
        await db.commit()
        return APIKeyResponse(
            id=key_id, key=api_key, name=data.name,
            created_at=now_iso(), last_used_at=None,
        )
    finally:
        await db.close()
