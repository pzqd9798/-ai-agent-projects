"""Admin API — 用户管理、Agent 管理、统计."""

import hashlib
import uuid
import json
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from app.models.database import get_db, AGENT_TEMPLATES

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def verify_admin(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(401, "Missing X-API-Key header")
    conn = get_db()
    row = conn.execute(
        "SELECT u.role FROM api_keys k JOIN users u ON k.user_id=u.id WHERE k.key=?",
        (x_api_key,)
    ).fetchone()
    conn.close()
    if not row or row["role"] != "admin":
        raise HTTPException(403, "Admin access required")
    return True


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
def get_stats(_=Depends(verify_admin)):
    conn = get_db()
    users = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
    agents = conn.execute("SELECT COUNT(*) as c FROM agents").fetchone()["c"]
    logs = conn.execute("SELECT COUNT(*) as c FROM audit_log").fetchone()["c"]
    conn.close()
    return {"users": users, "agents": agents, "audit_logs": logs}


# ---------------------------------------------------------------------------
# Agents CRUD
# ---------------------------------------------------------------------------

@router.get("/agents")
def list_agents(_=Depends(verify_admin)):
    conn = get_db()
    rows = conn.execute(
        "SELECT a.*, u.username FROM agents a JOIN users u ON a.user_id=u.id ORDER BY a.created_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


class CreateAgentRequest(BaseModel):
    name: str
    template: str = "custom"
    system_prompt: str = ""
    tools: list[str] = []
    model: str = "claude-sonnet-4-6"


@router.post("/agents")
def create_agent(req: CreateAgentRequest, _=Depends(verify_admin)):
    # Load template
    if req.template in AGENT_TEMPLATES and not req.system_prompt:
        t = AGENT_TEMPLATES[req.template]
        req.system_prompt = t["system_prompt"]
        req.tools = t["tools"]
        req.model = t["model"]

    conn = get_db()
    # Get admin user
    admin = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    aid = uuid.uuid4().hex[:12]
    conn.execute(
        "INSERT INTO agents (id, user_id, name, template, system_prompt, tools, model) VALUES (?,?,?,?,?,?,?)",
        (aid, admin["id"], req.name, req.template, req.system_prompt, json.dumps(req.tools), req.model)
    )
    conn.execute("INSERT INTO audit_log (user_id, agent_id, action, detail) VALUES (?,?,?,?)",
                 (admin["id"], aid, "create_agent", f"Created agent '{req.name}' from template '{req.template}'"))
    conn.commit()
    conn.close()
    return {"id": aid, "name": req.name}


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, _=Depends(verify_admin)):
    conn = get_db()
    conn.execute("DELETE FROM agents WHERE id=?", (agent_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

@router.get("/templates")
def list_templates(_=Depends(verify_admin)):
    return AGENT_TEMPLATES


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@router.get("/users")
def list_users(_=Depends(verify_admin)):
    conn = get_db()
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]


class CreateAPIKeyRequest(BaseModel):
    user_id: str
    name: str = ""


@router.post("/api-keys")
def create_api_key(req: CreateAPIKeyRequest, _=Depends(verify_admin)):
    key = "clawbot-" + uuid.uuid4().hex[:16]
    conn = get_db()
    conn.execute("INSERT INTO api_keys (key, user_id, name) VALUES (?,?,?)",
                 (key, req.user_id, req.name))
    conn.commit()
    conn.close()
    return {"key": key}
