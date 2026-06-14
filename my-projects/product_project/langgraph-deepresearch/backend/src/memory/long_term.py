"""Long-term memory — cross-session knowledge accumulation using SQLite.

Stores user preferences, frequently researched topics, and reusable findings.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models.db_models import Note, User

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Cross-session knowledge manager backed by the database."""

    def __init__(self, user_id: int, db: AsyncSession) -> None:
        self.user_id = user_id
        self.db = db
        self._preferences: dict[str, Any] = {}
        self._recent_topics: list[str] = []
        self._loaded = False

    async def load(self) -> None:
        """Load user preferences and recent topics from the database."""
        if self._loaded:
            return

        # Load conclusions (notes of type 'conclusion')
        result = await self.db.execute(
            select(Note)
            .where(Note.user_id == self.user_id, Note.note_type == "conclusion")
            .order_by(Note.updated_at.desc())
            .limit(10)
        )
        conclusions = result.scalars().all()
        self._recent_topics = [n.title for n in conclusions if n.title]

        # Load preferences from a special note
        result = await self.db.execute(
            select(Note)
            .where(Note.user_id == self.user_id, Note.note_type == "preference")
            .order_by(Note.updated_at.desc())
            .limit(1)
        )
        pref = result.scalar_one_or_none()
        if pref:
            try:
                self._preferences = json.loads(pref.content)
            except (json.JSONDecodeError, TypeError):
                self._preferences = {}

        self._loaded = True

    async def save_preferences(self, prefs: dict[str, Any]) -> None:
        """Persist user preferences."""
        self._preferences.update(prefs)
        content = json.dumps(self._preferences, ensure_ascii=False)

        result = await self.db.execute(
            select(Note).where(
                Note.user_id == self.user_id, Note.note_type == "preference"
            )
        )
        note = result.scalar_one_or_none()
        if note:
            note.content = content
        else:
            import secrets
            note = Note(
                user_id=self.user_id,
                note_uid=f"pref-{secrets.token_hex(4)}",
                title="User Preferences",
                note_type="preference",
                content=content,
            )
            self.db.add(note)
        await self.db.commit()

    async def add_research_topic(self, topic: str) -> None:
        """Record a researched topic for future reference."""
        if topic not in self._recent_topics:
            self._recent_topics.insert(0, topic)
            self._recent_topics = self._recent_topics[:20]  # cap

    async def build_context_text(self) -> str:
        """Build a context string of long-term knowledge for prompts."""
        if not self._loaded:
            await self.load()

        parts: list[str] = []
        if self._recent_topics:
            parts.append("## 历史研究主题\n")
            for topic in self._recent_topics[:5]:
                parts.append(f"- {topic}")
            parts.append("")

        if self._preferences:
            parts.append("## 用户偏好\n")
            for key, value in self._preferences.items():
                parts.append(f"- **{key}**: {value}")
            parts.append("")

        return "\n".join(parts)

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._preferences.get(key, default)
