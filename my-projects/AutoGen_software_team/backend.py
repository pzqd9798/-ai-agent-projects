"""FastAPI 后端 — 接收任务、运行团队、流式推送对话."""

import sys
import os
import json
import uuid
import asyncio
import queue
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from team.orchestrator import PRESET_TASKS, create_model_client
from team.agents import (
    create_product_manager,
    create_engineer,
    create_code_reviewer,
    create_user_proxy,
)
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import TextMessage, ToolCallMessage

app = FastAPI(title="AutoGen Team API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 任务状态存储
_task_store: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    task: str
    max_turns: int = 20
    preset: str = ""


class TaskStatus(BaseModel):
    task_id: str
    status: str  # "running" | "done" | "error"
    messages: list[dict] = []
    error: str = ""


# ---------------------------------------------------------------------------
# 流式团队运行器 — 收集每条消息并通过 queue 推送到 SSE
# ---------------------------------------------------------------------------

async def run_team_streaming(task: str, task_id: str, max_turns: int):
    """运行团队并将每条消息 push 到 task_store 的队列中."""
    store = _task_store.get(task_id)
    if not store:
        return
    msg_queue: queue.Queue = store["queue"]

    try:
        model_client = create_model_client()
        team = RoundRobinGroupChat(
            participants=[
                create_product_manager(model_client),
                create_engineer(model_client),
                create_code_reviewer(model_client),
                create_user_proxy(),
            ],
            termination_condition=TextMentionTermination("TERMINATE"),
            max_turns=max_turns,
        )

        store["status"] = "running"

        async for message in team.run_stream(task=task):
            if not hasattr(message, "source"):
                continue

            msg_data = {
                "role": message.source,
                "content": message.content if isinstance(message.content, str)
                           else str(message.content),
                "type": message.type if hasattr(message, "type") else "text",
            }
            store["messages"].append(msg_data)
            msg_queue.put(msg_data)

        store["status"] = "done"

    except Exception as exc:
        store["status"] = "error"
        store["error"] = str(exc)
        msg_queue.put({"role": "system", "content": f"Error: {exc}", "type": "error"})
    finally:
        msg_queue.put(None)  # 结束信号


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/presets")
async def list_presets():
    return {"presets": {k: v.split("\n")[0] for k, v in PRESET_TASKS.items()}}


@app.post("/api/run")
async def run_task(req: RunRequest):
    task_id = uuid.uuid4().hex[:12]

    # 确定任务文本
    task_text = PRESET_TASKS.get(req.preset, req.task)
    if not task_text.strip():
        raise HTTPException(400, "请提供任务描述或选择预设任务")

    _task_store[task_id] = {
        "status": "pending",
        "task": task_text,
        "messages": [],
        "error": "",
        "queue": queue.Queue(),
        "created_at": datetime.now().isoformat(),
    }

    # 后台运行
    asyncio.create_task(run_team_streaming(task_text, task_id, req.max_turns))

    return {"task_id": task_id, "status": "pending"}


@app.get("/api/stream/{task_id}")
async def stream_task(task_id: str):
    """SSE 流式推送团队对话."""
    store = _task_store.get(task_id)
    if not store:
        raise HTTPException(404, "任务不存在")

    async def generate():
        msg_queue = store["queue"]
        while True:
            try:
                msg = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: msg_queue.get(timeout=120)
                )
            except queue.Empty:
                yield f"data: {json.dumps({'role': 'system', 'content': '超时', 'type': 'timeout'})}\n\n"
                break

            if msg is None:
                break
            yield f"data: {json.dumps(msg, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/status/{task_id}")
async def task_status(task_id: str):
    store = _task_store.get(task_id)
    if not store:
        raise HTTPException(404, "任务不存在")
    return {
        "task_id": task_id,
        "status": store["status"],
        "message_count": len(store["messages"]),
        "error": store["error"],
    }


@app.get("/api/result/{task_id}")
async def task_result(task_id: str):
    store = _task_store.get(task_id)
    if not store:
        raise HTTPException(404, "任务不存在")
    return {
        "task_id": task_id,
        "task": store["task"],
        "status": store["status"],
        "messages": store["messages"],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "active_tasks": len(_task_store)}


def main():
    print("🤖 AutoGen Team API")
    print("   http://localhost:8001")
    print("   /docs — API 文档")
    uvicorn.run(app, host="0.0.0.0", port=8001)


if __name__ == "__main__":
    main()
