"""Transactional outbox.

Events are written to the `outbox` table in the *same database transaction* as the
state change that produced them. This guarantees that if the change commits, the event
is durably recorded — no lost triggers. A worker later reads unpublished rows and
delivers them, giving at-least-once semantics (handlers must be idempotent).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import DateTime, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, utcnow
from app.domain.events import DomainEvent
from app.domain.ids import new_id


class OutboxEntry(Base):
    __tablename__ = "outbox"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    event_name: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def enqueue(session: AsyncSession, event: DomainEvent) -> None:
    """Append an event to the outbox within the caller's transaction.

    Does not commit — the caller's unit of work owns the transaction boundary.
    """
    session.add(
        OutboxEntry(
            id=new_id(),
            user_id=event.user_id,
            event_name=event.name,
            payload=event.to_payload(),
        )
    )
