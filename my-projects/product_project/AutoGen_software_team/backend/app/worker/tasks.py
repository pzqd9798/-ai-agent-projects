"""异步任务 Worker — 基于 arq + Redis 的后台任务执行.

职责:
    - 执行耗时的 Agent 阶段任务
    - 自动重试失败任务
    - 结果持久化到数据库
"""

import asyncio
import time as time_mod
from dataclasses import dataclass, field
from datetime import datetime

from arq import create_pool
from arq.connections import RedisSettings

from app.config import config
from app.database import get_db, now_iso, new_id
from app.engine.agent_runner import AgentRunner, extract_code_blocks
from app.services.observability import get_observability


# ---------------------------------------------------------------------------
# 任务定义
# ---------------------------------------------------------------------------

async def execute_phase_task(ctx: dict, project_id: str, phase: str,
                              role_name: str, prompt: str,
                              template_name: str = "full-stack") -> dict:
    """后台执行 Agent 阶段任务.

    ctx 中包含:
        - project_id, phase, role_name, prompt, template_name
        - phase_id (已创建的阶段记录 ID)
    """
    obs = get_observability()
    phase_id = ctx.get("phase_id", "unknown")
    start_time = time_mod.perf_counter()

    obs.info("task_started", project_id=project_id[:8], phase=phase, role=role_name)

    try:
        # 更新阶段状态为 running
        db = await get_db()
        try:
            await db.execute(
                "UPDATE phases SET status='running', started_at=? WHERE id=?",
                (now_iso(), phase_id),
            )
            await db.commit()
        finally:
            await db.close()

        # 执行 Agent
        runner = AgentRunner(template_name)
        output = await runner.call_agent(role_name, prompt)

        elapsed_ms = (time_mod.perf_counter() - start_time) * 1000
        tokens_used = (len(prompt) + len(output)) // 4

        # 持久化结果
        db = await get_db()
        try:
            await db.execute(
                """UPDATE phases SET output_text=?, status='done',
                   finished_at=?, tokens_used=? WHERE id=?""",
                (output, now_iso(), tokens_used, phase_id),
            )

            # 提取并保存代码产物
            code_blocks = extract_code_blocks(output)
            for i, block in enumerate(code_blocks):
                file_ext = {"python": "py", "javascript": "js", "html": "html",
                           "css": "css", "bash": "sh"}
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
                (next_status.get(phase, "draft"), now_iso(), project_id),
            )
            await db.commit()
        finally:
            await db.close()

        obs.record_phase_execution(
            project_id, phase, role_name, elapsed_ms, tokens_used, True
        )

        return {"ok": True, "output": output[:200] + "...", "tokens": tokens_used}

    except Exception as e:
        elapsed_ms = (time_mod.perf_counter() - start_time) * 1000
        obs.record_phase_execution(
            project_id, phase, role_name, elapsed_ms, 0, False
        )
        obs.error("task_failed", project_id=project_id[:8], phase=phase, error=str(e))

        # 更新阶段为失败
        db = await get_db()
        try:
            await db.execute(
                "UPDATE phases SET status='failed', error_message=?, finished_at=? WHERE id=?",
                (str(e), now_iso(), phase_id),
            )
            await db.commit()
        finally:
            await db.close()

        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Worker 配置
# ---------------------------------------------------------------------------

class WorkerSettings:
    """arq Worker 配置."""
    functions = [execute_phase_task]
    redis_settings = RedisSettings.from_dsn(config.redis.url)
    max_jobs = 20
    job_timeout = 600  # 10 分钟超时
    keep_result = 3600  # 结果保留 1 小时
    poll_delay = 0.5


async def enqueue_phase(project_id: str, phase: str, role_name: str,
                         prompt: str, template_name: str,
                         phase_id: str) -> str:
    """将阶段执行任务加入队列, 返回 job_id."""
    pool = await create_pool(WorkerSettings.redis_settings)
    job = await pool.enqueue_job(
        "execute_phase_task",
        project_id, phase, role_name, prompt, template_name,
        _phase_id=phase_id,  # 通过 ctx 传递
        _job_id=f"{project_id[:8]}-{phase}-{phase_id[:8]}",
    )
    return job.job_id


async def get_job_result(job_id: str) -> dict | None:
    """查询任务执行结果."""
    pool = await create_pool(WorkerSettings.redis_settings)
    job = await pool.get_job(job_id)
    if job is None:
        return None
    if job.result_info is None:
        return {"status": "pending"}
    if job.result_info.finish_time is None:
        return {"status": "running"}
    return {"status": "done", "result": job.result_info.result}
