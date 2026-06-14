"""WebSocket SSE streaming — real-time research progress with token-level events."""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Configuration
from database import get_db
from models.db_models import ResearchMessage, ResearchSession, User
from api.auth import get_current_user
from models.schemas import ResearchRequest
from security.input_guard import sanitize_input
from services.observability import get_logger, get_metrics

router = APIRouter(prefix="/ws", tags=["流式"])

logger = get_logger()
metrics = get_metrics()


@router.post("/research/stream")
async def research_stream(
    req: ResearchRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SSE streaming deep research — real-time progress updates."""
    t0 = time.time()

    # Input guard
    guard = sanitize_input(req.topic)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)
    topic = guard.sanitized or req.topic

    # Create session
    session = ResearchSession(
        user_id=user.id,
        topic=topic,
        search_api=req.search_api,
        status="running",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    config = Configuration.from_env()
    if req.search_api:
        config.search_api = req.search_api
    if req.max_loops:
        config.max_web_research_loops = req.max_loops

    async def event_generator() -> AsyncIterator[str]:
        nonlocal session
        try:
            from agent import DeepResearchAgent

            agent = DeepResearchAgent(config=config)

            # Track events for DB persistence
            event_count = 0

            async for event in agent.run_stream(topic):
                event_count += 1
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                # Periodically persist the latest report
                if event.get("type") == "final_report":
                    session.status = "completed"
                    session.report_markdown = event.get("report", "")
                    session.todo_items_json = json.dumps(
                        [
                            {
                                "id": t.id, "title": t.title,
                                "intent": t.intent, "query": t.query,
                                "status": t.status, "summary": t.summary,
                                "sources_summary": t.sources_summary,
                                "note_id": t.note_id, "note_path": t.note_path,
                            }
                            for t in (getattr(agent, '_last_state', None) and
                                       getattr(agent._last_state, 'todo_items', None) or [])
                        ],
                        ensure_ascii=False,
                    )
                    if event.get("note_id"):
                        session.report_note_id = event["note_id"]
                    session.elapsed_ms = int((time.time() - t0) * 1000)
                    await db.commit()

                if event.get("type") == "error":
                    session.status = "failed"
                    session.error_message = str(event.get("detail", ""))
                    await db.commit()

                if event.get("type") == "done":
                    break

            # Finalize session if not already done
            if session.status == "running":
                session.status = "completed"
                session.elapsed_ms = int((time.time() - t0) * 1000)
                await db.commit()

            metrics.incr("research_stream_completed")
            logger.info(
                "stream_done", session_id=session.id,
                events=event_count,
                elapsed_ms=session.elapsed_ms,
            )

        except asyncio.CancelledError:
            session.status = "cancelled"
            await db.commit()
            yield f"data: {json.dumps({'type': 'status', 'message': '研究已取消'}, ensure_ascii=False)}\n\n"

        except Exception as exc:
            logger.exception("Streaming research failed")
            session.status = "failed"
            session.error_message = str(exc)
            await db.commit()
            metrics.incr("research_stream_failed")
            error_payload = {"type": "error", "detail": str(exc)}
            yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research/stream")
async def research_stream_get(
    topic: str = Query(..., min_length=1),
    search_api: str | None = Query(None),
    max_loops: int | None = Query(None, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """GET-based SSE streaming (convenience, e.g. for EventSource in browser)."""
    req = ResearchRequest(
        topic=topic,
        search_api=search_api,
        max_loops=max_loops,
    )
    return await research_stream(req, user=user, db=db)
