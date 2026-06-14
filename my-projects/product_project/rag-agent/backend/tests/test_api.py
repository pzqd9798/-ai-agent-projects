"""API 集成测试 — 完整流程验证."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

import pytest
pytestmark = [pytest.mark.asyncio]


@pytest_asyncio.fixture
async def client():
    """创建异步 HTTP 测试客户端."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# 基础
# ---------------------------------------------------------------------------

async def test_health(client):
    """健康检查."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"


async def test_root(client):
    """首页."""
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "RAG" in resp.text


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------

async def test_register_and_login(client):
    """注册 → 登录 → 获取用户信息."""
    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "testuser", "password": "test123456"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "api_key" not in data  # API key 在 /me 获取

    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 获取用户信息
    resp = await client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["username"] == "testuser"
    assert "api_key" in resp.json()


async def test_unauthorized_access(client):
    """未认证访问被拒绝."""
    resp = await client.get("/api/knowledge")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 知识库 CRUD
# ---------------------------------------------------------------------------

async def test_knowledge_base_crud(client):
    """知识库创建 → 列表 → 更新 → 删除."""
    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "kb_user", "password": "test123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建知识库
    resp = await client.post("/api/knowledge", json={
        "name": "Test KB",
        "description": "测试知识库",
        "tags": ["test", "demo"],
    }, headers=headers)
    assert resp.status_code == 200
    kb = resp.json()
    assert kb["name"] == "Test KB"
    assert kb["document_count"] == 0
    kb_id = kb["id"]

    # 列表
    resp = await client.get("/api/knowledge", headers=headers)
    assert resp.status_code == 200
    kbs = resp.json()
    assert len(kbs) >= 1

    # 获取详情
    resp = await client.get(f"/api/knowledge/{kb_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == kb_id

    # 更新
    resp = await client.put(f"/api/knowledge/{kb_id}", json={
        "name": "Updated KB",
        "description": "更新后的描述",
    }, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated KB"

    # 删除
    resp = await client.delete(f"/api/knowledge/{kb_id}", headers=headers)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 文档上传
# ---------------------------------------------------------------------------

async def test_document_upload(client):
    """上传 + 列表 + 删除文档."""
    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "doc_user", "password": "test123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建知识库
    resp = await client.post("/api/knowledge", json={
        "name": "Doc KB", "description": "文档测试", "tags": [],
    }, headers=headers)
    kb_id = resp.json()["id"]

    # 上传 txt 文件
    import tempfile
    import os

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("这是一个测试文档的内容。它包含足够多的文本来满足最小分块要求。" * 10)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            resp = await client.post(
                "/api/documents/upload",
                files={"file": ("test.txt", f, "text/plain")},
                data={"kb_id": kb_id},
                headers=headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"

        # 文档列表
        resp = await client.get(
            f"/api/documents?kb_id={kb_id}", headers=headers
        )
        assert resp.status_code == 200
        docs = resp.json()
        assert len(docs) >= 1

        # 删除文档
        doc_id = docs[0]["id"]
        resp = await client.delete(
            f"/api/documents/{doc_id}?kb_id={kb_id}", headers=headers
        )
        assert resp.status_code == 200
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# RAG 问答
# ---------------------------------------------------------------------------

async def test_rag_chat(client):
    """RAG 问答 (需要上传文档)."""
    import os
    import tempfile

    # 注册
    resp = await client.post("/api/auth/register", json={
        "username": "rag_user", "password": "test123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 创建知识库
    resp = await client.post("/api/knowledge", json={
        "name": "RAG KB",
        "description": "RAG 测试知识库，包含关于 Python 的文档",
        "tags": ["python"],
    }, headers=headers)
    kb_id = resp.json()["id"]

    # 上传包含 Python 信息的 txt 文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write(
            "Python 是一种高级编程语言，由 Guido van Rossum 于 1991 年创建。"
            "Python 以简洁优雅的语法著称，广泛用于 Web 开发、数据科学、人工智能等领域。"
            "Python 3 是最新的主要版本。"
            "pip 是 Python 的包管理工具。"
            "FastAPI 是一个现代 Python Web 框架，基于 Starlette 和 Pydantic。"
        )
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            resp = await client.post(
                "/api/documents/upload",
                files={"file": ("python_info.txt", f, "text/plain")},
                data={"kb_id": kb_id},
                headers=headers,
            )
        assert resp.status_code == 200

        # RAG 问答 (需要 LLM API key)
        if os.getenv("ANTHROPIC_API_KEY"):
            resp = await client.post("/api/chat", json={
                "question": "Python 是什么时候创建的？谁创建的？",
                "kb_id": kb_id,
                "top_k": 3,
            }, headers=headers, timeout=120.0)
            assert resp.status_code == 200
            data = resp.json()
            assert "answer" in data
            assert len(data["answer"]) > 0
            assert data["retrieved_count"] > 0
            assert data["sources"] is not None
        else:
            print("跳过: 未配置 ANTHROPIC_API_KEY, RAG 问答测试未运行")
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 纯检索
# ---------------------------------------------------------------------------

async def test_search(client):
    """纯语义搜索 (不需要 LLM)."""
    import os
    import tempfile

    resp = await client.post("/api/auth/register", json={
        "username": "search_user", "password": "test123456"
    })
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post("/api/knowledge", json={
        "name": "Search KB",
        "description": "搜索测试知识库，包含关于机器学习的文档",
        "tags": ["ml"],
    }, headers=headers)
    kb_id = resp.json()["id"]

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("机器学习是人工智能的一个分支。深度学习是机器学习的一个子集。神经网络是深度学习的基础。" * 5)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as f:
            resp = await client.post(
                "/api/documents/upload",
                files={"file": ("ml_info.txt", f, "text/plain")},
                data={"kb_id": kb_id},
                headers=headers,
            )
        assert resp.status_code == 200

        # 搜索
        resp = await client.post("/api/documents/search", json={
            "query": "什么是机器学习",
            "kb_id": kb_id,
            "top_k": 3,
        }, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["results"]) >= 1
        assert "score" in data["results"][0]
    finally:
        os.unlink(tmp_path)
