"""WebSocket API — SSE 流式推送 Agent 执行过程."""

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query

from app.database import get_db
from app.engine.agent_runner import AgentRunner

router = APIRouter()


@router.websocket("/ws/projects/{project_id}/stream")
async def stream_phase(
    websocket: WebSocket,
    project_id: str,
    phase: str = Query("plan"),
    token: str = Query(...),
):
    """WebSocket 流式推送 Agent 的阶段执行过程.

    客户端接收 JSON 事件:
        {"type": "phase_start", "phase": "plan", "role": "ProductManager"}
        {"type": "content", "phase": "plan", "role": "ProductManager", "text": "..."}
        {"type": "phase_complete", "phase": "plan", "role": "ProductManager"}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    try:
        # 验证 token
        import jwt as pyjwt
        from app.config import config as app_config
        try:
            payload = pyjwt.decode(
                token, app_config.auth.jwt_secret,
                algorithms=[app_config.auth.jwt_algorithm]
            )
        except Exception:
            await websocket.send_json({"type": "error", "message": "认证失败"})
            await websocket.close()
            return

        # 获取项目上下文
        db = await get_db()
        try:
            row = await db.execute_fetchall(
                "SELECT * FROM projects WHERE id=? AND user_id=?",
                (project_id, payload["sub"])
            )
            if not row:
                await websocket.send_json({"type": "error", "message": "项目不存在"})
                await websocket.close()
                return
            proj = row[0]
        finally:
            await db.close()

        # 获取历史阶段上下文
        db = await get_db()
        try:
            prev_rows = await db.execute_fetchall(
                "SELECT phase, output_text FROM phases WHERE project_id=? AND status='done' ORDER BY finished_at",
                (project_id,)
            )
            context = {"plan": "", "code": "", "review": ""}
            for r in prev_rows:
                context[r[0]] = r[1] or ""
        finally:
            await db.close()

        # 构建 prompt
        task = proj[3]
        if phase == "plan":
            prompt = f"请分析以下开发任务的需求：\n\n{task}"
            role_name = "ProductManager"
        elif phase == "code":
            prompt = f"## 产品需求分析\n{context['plan']}\n\n## 开发任务\n{task}\n\n请编写完整的可运行代码。"
            role_name = "Engineer"
        else:
            prompt = f"## 任务\n{task}\n\n## 需求分析\n{context['plan']}\n\n## 代码\n{context['code'][:5000]}\n\n请审查代码质量。"
            role_name = "CodeReviewer"

        # 流式执行
        runner = AgentRunner(proj[4])
        await websocket.send_json({
            "type": "phase_start", "phase": phase, "role": role_name,
            "project_id": project_id,
        })

        async for chunk in runner.run_phase_stream(role_name, prompt):
            await websocket.send_json({
                "type": "content", "phase": phase, "role": role_name,
                "text": chunk,
            })

        await websocket.send_json({
            "type": "phase_complete", "phase": phase, "role": role_name,
            "project_id": project_id,
        })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
