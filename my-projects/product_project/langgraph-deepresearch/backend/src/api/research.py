"""Research API — multi-tenant deep research with session management."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Configuration
from database import get_db
from models.db_models import (
    ResearchMessage,
    ResearchSession,
    SearchResult,
    User,
)
from api.auth import get_current_user
from models.schemas import (
    ResearchRequest,
    ResearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    SessionListResponse,
    SessionResponse,
)
from search.backends import search as execute_search
from security.input_guard import sanitize_input
from services.observability import get_logger, get_metrics

router = APIRouter(prefix="/api/research", tags=["研究"])

logger = get_logger()
metrics = get_metrics()


# ---------------------------------------------------------------------------
# Session management helpers
# ---------------------------------------------------------------------------


async def _get_session(
    session_id: int, user_id: int, db: AsyncSession
) -> ResearchSession | None:
    result = await db.execute(
        select(ResearchSession).where(
            ResearchSession.id == session_id,
            ResearchSession.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=ResearchResponse)
async def start_research(
    req: ResearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Launch a new deep research task (synchronous, returns report)."""
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

    try:
        # Execute research using the existing agent (backward compat)
        from agent import DeepResearchAgent

        config = Configuration.from_env()
        if req.search_api:
            config.search_api = req.search_api
        if req.max_loops:
            config.max_web_research_loops = req.max_loops

        agent = DeepResearchAgent(config=config)
        result = agent.run(topic)

        # Persist results
        session.status = "completed"
        session.report_markdown = result.report_markdown or result.running_summary or ""
        session.todo_items_json = json.dumps(
            [
                {
                    "id": t.id,
                    "title": t.title,
                    "intent": t.intent,
                    "query": t.query,
                    "status": t.status,
                    "summary": t.summary,
                    "sources_summary": t.sources_summary,
                    "note_id": t.note_id,
                    "note_path": t.note_path,
                }
                for t in (result.todo_items or [])
            ],
            ensure_ascii=False,
        )
        if result.report_note_id:
            session.report_note_id = result.report_note_id

        elapsed = (time.time() - t0) * 1000
        session.elapsed_ms = int(elapsed)

        await db.commit()

        metrics.incr("research_completed")
        logger.info("research_done", session_id=session.id, elapsed_ms=int(elapsed))

        return ResearchResponse(
            session_id=session.id,
            topic=topic,
            report_markdown=session.report_markdown or "",
            todo_items=json.loads(session.todo_items_json or "[]"),
            elapsed_ms=int(elapsed),
        )

    except Exception as exc:
        session.status = "failed"
        session.error_message = str(exc)
        await db.commit()
        metrics.incr("research_failed")
        logger.error("research_failed", session_id=session.id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"研究失败: {exc}")


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
):
    """List the user's research sessions."""
    # Count
    count_result = await db.execute(
        select(func.count(ResearchSession.id)).where(
            ResearchSession.user_id == user.id
        )
    )
    total = count_result.scalar() or 0

    # Fetch
    result = await db.execute(
        select(ResearchSession)
        .where(ResearchSession.user_id == user.id)
        .order_by(desc(ResearchSession.updated_at))
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()

    items = []
    for s in sessions:
        todo_count = 0
        if s.todo_items_json:
            try:
                todo_count = len(json.loads(s.todo_items_json))
            except (json.JSONDecodeError, TypeError):
                pass

        items.append(
            SessionResponse(
                id=s.id,
                topic=s.topic,
                status=s.status,
                search_api=s.search_api,
                report_markdown=s.report_markdown,
                todo_count=todo_count,
                elapsed_ms=s.elapsed_ms,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )

    return SessionListResponse(sessions=items, total=total)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single research session."""
    s = await _get_session(session_id, user.id, db)
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")

    todo_count = 0
    if s.todo_items_json:
        try:
            todo_count = len(json.loads(s.todo_items_json))
        except (json.JSONDecodeError, TypeError):
            pass

    return SessionResponse(
        id=s.id,
        topic=s.topic,
        status=s.status,
        search_api=s.search_api,
        report_markdown=s.report_markdown,
        todo_count=todo_count,
        elapsed_ms=s.elapsed_ms,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a research session and its associated data."""
    s = await _get_session(session_id, user.id, db)
    if not s:
        raise HTTPException(status_code=404, detail="会话不存在")
    await db.delete(s)
    await db.commit()
    return {"message": "会话已删除"}


# ---------------------------------------------------------------------------
# Pure search endpoint
# ---------------------------------------------------------------------------


@router.post("/search", response_model=SearchResponse)
async def search_endpoint(
    req: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Execute a search without launching a full research workflow."""
    t0 = time.time()
    config = Configuration.from_env()

    raw = execute_search(req.query, config, max_results=req.max_results)

    results = []
    for r in raw.get("results", []):
        results.append(
            SearchResultItem(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                backend=raw.get("backend", ""),
            )
        )

    elapsed = (time.time() - t0) * 1000

    # Save to DB if session provided
    if req.session_id:
        sr = SearchResult(
            session_id=req.session_id,
            query=req.query,
            backend=raw.get("backend", ""),
            results_json=json.dumps(results, ensure_ascii=False, default=str),
            answer_text=raw.get("answer"),
            notices_json=json.dumps(raw.get("notices", []), ensure_ascii=False),
        )
        db.add(sr)
        await db.commit()

    return SearchResponse(
        query=req.query,
        results=results,
        backend=raw.get("backend", ""),
        answer=raw.get("answer"),
        total=len(results),
        elapsed_ms=round(elapsed, 1),
    )
