"""阶段执行 API — 驱动 plan/code/review 三阶段流程."""

import asyncio
import time as time_mod
from fastapi import APIRouter, HTTPException, Depends

from app.database import get_db, now_iso, new_id
from app.models import (
    PhaseExecuteRequest, PhaseResponse, ArtifactResponse, ProjectResponse,
)
from app.api.auth import get_current_user
from app.engine.agent_runner import AgentRunner, extract_code_blocks

router = APIRouter(prefix="/api/projects", tags=["阶段执行"])


def _build_prompt(phase: str, task: str, plan: str, code: str, feedback: str) -> str:
    """根据上下文构建阶段 prompt."""
    if phase == "plan":
        return f"请分析以下开发任务的需求：\n\n{task}"

    elif phase == "code":
        prompt = f"## 产品需求分析\n{plan}\n\n## 开发任务\n{task}"
        if feedback:
            prompt += f"\n\n## 用户反馈\n{feedback}\n请根据反馈调整代码。"
        prompt += "\n\n请编写完整的可运行代码。代码用 ```python 和 ``` 包裹。"
        return prompt

    elif phase == "review":
        prompt = f"## 任务\n{task}\n\n## 需求分析\n{plan}\n\n## 代码\n{code[:5000]}"
        if feedback:
            prompt += f"\n\n## 用户反馈\n{feedback}\n请针对反馈重新审查。"
        prompt += "\n\n请审查代码质量、安全性和最佳实践，给出具体的改进建议。"
        return prompt

    return task


@router.post("/{project_id}/phases/{phase}", response_model=PhaseResponse)
async def execute_phase(
    project_id: str,
    phase: str,
    data: PhaseExecuteRequest,
    user=Depends(get_current_user),
):
    """执行项目的一个阶段 (plan/code/review)."""
    db = await get_db()
    try:
        # 确认项目归属
        proj_row = await db.execute_fetchall(
            "SELECT * FROM projects WHERE id=? AND user_id=?",
            (project_id, user["id"])
        )
        if not proj_row:
            raise HTTPException(404, "项目不存在")

        proj = proj_row[0]

        # 获取历史阶段上下文
        prev_rows = await db.execute_fetchall(
            "SELECT phase, output_text FROM phases WHERE project_id=? AND status='done' ORDER BY finished_at",
            (project_id,)
        )
        context = {"plan": "", "code": "", "review": ""}
        for r in prev_rows:
            context[r[0]] = r[1] or ""

        # 构建 prompt
        prompt = _build_prompt(
            phase, proj[3], context["plan"], context["code"], data.feedback or ""
        )

        # 确定角色
        role_map = {"plan": "ProductManager", "code": "Engineer", "review": "CodeReviewer"}
        role_name = role_map[phase]

        # 创建阶段记录
        phase_id = new_id()
        started_at = now_iso()
        await db.execute(
            """INSERT INTO phases(id, project_id, phase, role, input_prompt, status, started_at)
               VALUES(?,?,?,?,?,'running',?)""",
            (phase_id, project_id, phase, role_name, prompt, started_at),
        )
        await db.commit()

        # 执行 Agent
        start_time = time_mod.perf_counter()
        try:
            runner = AgentRunner(proj[4])  # template_id
            output = await runner.call_agent(role_name, prompt)
            elapsed = (time_mod.perf_counter() - start_time) * 1000

            # 计算 token 近似值
            tokens_used = (len(prompt) + len(output)) // 4

            # 更新阶段记录
            finished_at = now_iso()
            await db.execute(
                """UPDATE phases SET output_text=?, status='done', finished_at=?,
                   tokens_used=? WHERE id=?""",
                (output, finished_at, tokens_used, phase_id),
            )

            # 提取代码并保存为产物
            code_blocks = extract_code_blocks(output)
            for i, block in enumerate(code_blocks):
                file_ext = {"python": "py", "javascript": "js", "html": "html",
                           "css": "css", "bash": "sh", "text": "txt"}
                ext = file_ext.get(block["language"], "txt")
                file_path = f"{phase}/generated_{i+1}.{ext}"
                await db.execute(
                    """INSERT INTO artifacts(id, project_id, phase_id, file_path, content, language)
                       VALUES(?,?,?,?,?,?)""",
                    (new_id(), project_id, phase_id, file_path, block["code"], block["language"]),
                )

            # 更新项目状态
            next_status = {"plan": "planning", "code": "coding", "review": "done"}
            await db.execute(
                "UPDATE projects SET status=?, updated_at=? WHERE id=?",
                (next_status.get(phase, "draft"), finished_at, project_id),
            )
            await db.commit()

            return PhaseResponse(
                id=phase_id, project_id=project_id, phase=phase, role=role_name,
                input_prompt=prompt, output_text=output, status="done",
                started_at=started_at, finished_at=finished_at,
                tokens_used=tokens_used,
            )

        except Exception as e:
            await db.execute(
                "UPDATE phases SET status='failed', error_message=? WHERE id=?",
                (str(e), phase_id),
            )
            await db.commit()
            raise HTTPException(500, f"阶段执行失败: {str(e)}")

    finally:
        await db.close()


@router.get("/{project_id}/phases", response_model=list[PhaseResponse])
async def list_phases(project_id: str, user=Depends(get_current_user)):
    """获取项目的所有阶段记录."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM phases WHERE project_id=? ORDER BY started_at",
            (project_id,)
        )
        return [
            PhaseResponse(
                id=r[0], project_id=r[1], phase=r[2], role=r[3],
                input_prompt=r[4] or "", output_text=r[5], status=r[6],
                started_at=r[7], finished_at=r[8], tokens_used=r[9] or 0,
                error_message=r[10],
            )
            for r in rows
        ]
    finally:
        await db.close()


@router.get("/{project_id}/artifacts", response_model=list[ArtifactResponse])
async def list_artifacts(project_id: str, user=Depends(get_current_user)):
    """获取项目的所有产物."""
    db = await get_db()
    try:
        rows = await db.execute_fetchall(
            "SELECT * FROM artifacts WHERE project_id=? ORDER BY created_at",
            (project_id,)
        )
        return [
            ArtifactResponse(
                id=r[0], project_id=r[1], file_path=r[3], content=r[4],
                language=r[5] or "text", version=r[6] or 1, created_at=r[7],
            )
            for r in rows
        ]
    finally:
        await db.close()
