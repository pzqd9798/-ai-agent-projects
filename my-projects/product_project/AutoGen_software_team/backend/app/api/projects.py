"""项目 API — 创建/查询/更新/删除项目."""

import asyncio
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db, now_iso, new_id
from app.models import (
    ProjectCreate, ProjectUpdate, ProjectResponse, DashboardStats,
)
from app.api.auth import get_current_user

router = APIRouter(prefix="/api/projects", tags=["项目"])


@router.post("", response_model=ProjectResponse)
async def create_project(data: ProjectCreate, user=Depends(get_current_user)):
    """创建新项目."""
    db = await get_db()
    try:
        project_id = new_id()
        now = now_iso()
        await db.execute(
            """INSERT INTO projects(id, user_id, name, description, template_id, created_at, updated_at)
               VALUES(?,?,?,?,?,?,?)""",
            (project_id, user["id"], data.name, data.description,
             data.template_id, now, now),
        )
        await db.commit()

        return ProjectResponse(
            id=project_id, user_id=user["id"], name=data.name,
            description=data.description, template_id=data.template_id,
            status="draft", created_at=now, updated_at=now, phase_count=0,
        )
    finally:
        await db.close()


@router.get("", response_model=list[ProjectResponse])
async def list_projects(user=Depends(get_current_user)):
    """获取当前用户的所有项目."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            """SELECT p.*, COUNT(ph.id) as phase_count
               FROM projects p LEFT JOIN phases ph ON p.id = ph.project_id
               WHERE p.user_id = ?
               GROUP BY p.id
               ORDER BY p.updated_at DESC""",
            (user["id"],)
        )
        return [
            ProjectResponse(
                id=r[0], user_id=r[1], name=r[2], description=r[3],
                template_id=r[4], status=r[5], created_at=r[6],
                updated_at=r[7], phase_count=r[8],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, user=Depends(get_current_user)):
    """获取项目详情."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            """SELECT p.*, COUNT(ph.id) as phase_count
               FROM projects p LEFT JOIN phases ph ON p.id = ph.project_id
               WHERE p.id = ? AND p.user_id = ?
               GROUP BY p.id""",
            (project_id, user["id"])
        )
        if not row:
            raise HTTPException(404, "项目不存在")
        r = row[0]
        return ProjectResponse(
            id=r[0], user_id=r[1], name=r[2], description=r[3],
            template_id=r[4], status=r[5], created_at=r[6],
            updated_at=r[7], phase_count=r[8],
        )
    finally:
        await db.close()


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, data: ProjectUpdate,
                         user=Depends(get_current_user)):
    """更新项目."""
    db = await get_db()
    try:
        # 确认归属
        row = await db.execute_fetchall(
            "SELECT * FROM projects WHERE id=? AND user_id=?",
            (project_id, user["id"])
        )
        if not row:
            raise HTTPException(404, "项目不存在")

        updates = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.status is not None:
            updates["status"] = data.status

        if updates:
            updates["updated_at"] = now_iso()
            set_clause = ", ".join(f"{k}=:{k}" for k in updates)
            params = {**updates, "id": project_id}
            await db.execute(
                f"UPDATE projects SET {set_clause} WHERE id=:id", params
            )
            await db.commit()

        # 重新查询
        row = await db.execute_fetchall(
            "SELECT p.*, COUNT(ph.id) FROM projects p LEFT JOIN phases ph ON p.id=ph.project_id WHERE p.id=? GROUP BY p.id",
            (project_id,)
        )
        r = row[0]
        return ProjectResponse(
            id=r[0], user_id=r[1], name=r[2], description=r[3],
            template_id=r[4], status=r[5], created_at=r[6],
            updated_at=r[7], phase_count=r[8],
        )
    finally:
        await db.close()


@router.delete("/{project_id}")
async def delete_project(project_id: str, user=Depends(get_current_user)):
    """删除项目 (级联删除所有阶段、产物、版本)."""
    db = await get_db()
    try:
        row = await db.execute_fetchall(
            "SELECT id FROM projects WHERE id=? AND user_id=?",
            (project_id, user["id"])
        )
        if not row:
            raise HTTPException(404, "项目不存在")

        for table in ["versions", "artifacts", "phases"]:
            await db.execute(f"DELETE FROM {table} WHERE project_id=?", (project_id,))
        await db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        await db.commit()
        return {"ok": True}
    finally:
        await db.close()
