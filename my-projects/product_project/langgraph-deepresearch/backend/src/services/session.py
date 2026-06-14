"""Session service — manages research session lifecycle and persistence."""

from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Note, ResearchMessage, ResearchSession, SearchResult, User


class SessionService:
    """Service for managing research session CRUD and persistence."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(
        self,
        user_id: int,
        topic: str,
        search_api: str = "",
    ) -> ResearchSession:
        session = ResearchSession(
            user_id=user_id,
            topic=topic,
            search_api=search_api,
            status="pending",
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get(self, session_id: int, user_id: int) -> ResearchSession | None:
        result = await self.db.execute(
            select(ResearchSession).where(
                ResearchSession.id == session_id,
                ResearchSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(
        self, user_id: int, limit: int = 20, offset: int = 0
    ) -> tuple[list[ResearchSession], int]:
        count_result = await self.db.execute(
            select(func.count(ResearchSession.id)).where(
                ResearchSession.user_id == user_id
            )
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(desc(ResearchSession.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all()), total

    async def update_status(
        self,
        session: ResearchSession,
        status: str,
        **kwargs: Any,
    ) -> None:
        session.status = status
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        await self.db.commit()

    async def delete(self, session: ResearchSession) -> None:
        await self.db.delete(session)
        await self.db.commit()

    async def log_event(
        self,
        session_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> ResearchMessage:
        msg = ResearchMessage(
            session_id=session_id,
            event_type=event_type,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
        )
        self.db.add(msg)
        await self.db.commit()
        return msg

    async def get_events(
        self, session_id: int, user_id: int
    ) -> list[ResearchMessage]:
        # Verify ownership
        session = await self.get(session_id, user_id)
        if not session:
            return []

        result = await self.db.execute(
            select(ResearchMessage)
            .where(ResearchMessage.session_id == session_id)
            .order_by(ResearchMessage.created_at)
        )
        return list(result.scalars().all())
