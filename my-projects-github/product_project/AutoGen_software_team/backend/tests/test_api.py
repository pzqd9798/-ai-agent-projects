"""API 集成测试 — 完整流程验证."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.database import init_db


@pytest.fixture(autouse=True)
async def setup_db():
    """每个测试前初始化数据库."""
    await init_db()


@pytest.fixture
async def client():
    """创建异步 HTTP 测试客户端."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_health(client):
    """健康检查."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_register_and_login(client):
    """注册 → 登录 → 获取用户信息."""
    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "testuser", "password": "test123456"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 获取当前用户
    resp = await client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"


@pytest.mark.asyncio
async def test_full_workflow(client):
    """完整工作流: 注册 → 创建项目 → 查看项目."""
    # 1. 注册
    resp = await client.post("/api/auth/register", json={
        "username": "dev_user", "password": "dev123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 创建项目
    resp = await client.post("/api/projects", json={
        "name": "测试项目",
        "description": "这是一个测试项目的需求描述，应该足够长以满足最小长度要求。",
        "template_id": "cli-tool",
    }, headers=headers)
    assert resp.status_code == 200
    proj = resp.json()
    assert proj["name"] == "测试项目"
    project_id = proj["id"]

    # 3. 获取项目列表
    resp = await client.get("/api/projects", headers=headers)
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) >= 1

    # 4. 获取项目详情
    resp = await client.get(f"/api/projects/{project_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == project_id


@pytest.mark.asyncio
async def test_phase_execution(client):
    """阶段执行 (需要有效的 API Key 和 AutoGen)."""
    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "phase_user", "password": "phase123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建项目
    resp = await client.post("/api/projects", json={
        "name": "Phase Test",
        "description": "测试阶段执行的项目需求描述，需要足够长以满足验证要求。",
        "template_id": "cli-tool",
    }, headers=headers)
    project_id = resp.json()["id"]

    # 执行 plan 阶段 (需要 LLM API key 配置)
    import os
    if os.getenv("LLM_API_KEY"):
        resp = await client.post(
            f"/api/projects/{project_id}/phases/plan",
            json={"phase": "plan"},
            headers=headers,
            timeout=120.0,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"
        assert resp.json()["phase"] == "plan"
    else:
        print("跳过: 未配置 LLM_API_KEY, 阶段执行测试未运行")


@pytest.mark.asyncio
async def test_unauthorized_access(client):
    """未认证访问被拒绝."""
    resp = await client.get("/api/projects")
    assert resp.status_code == 401
