"""Notification data access."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import NotificationStatus, NotificationType
from app.modules.notifications.models import (
    NotificationEvent,
    NotificationPreference,
    NotificationRule,
)


async def list_rules(session: AsyncSession, user_id: uuid.UUID) -> Sequence[NotificationRule]:
    stmt = select(NotificationRule).where(NotificationRule.user_id == user_id)
    return (await session.execute(stmt)).scalars().all()


async def get_rule(
    session: AsyncSession, user_id: uuid.UUID, type_: NotificationType
) -> NotificationRule | None:
    stmt = select(NotificationRule).where(
        NotificationRule.user_id == user_id, NotificationRule.type == type_
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def add_rule(session: AsyncSession, rule: NotificationRule) -> None:
    session.add(rule)


async def get_preference(
    session: AsyncSession, user_id: uuid.UUID
) -> NotificationPreference | None:
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


def add_preference(session: AsyncSession, pref: NotificationPreference) -> None:
    session.add(pref)


async def event_exists(session: AsyncSession, user_id: uuid.UUID, dedupe_key: str) -> bool:
    stmt = select(NotificationEvent.id).where(
        NotificationEvent.user_id == user_id, NotificationEvent.dedupe_key == dedupe_key
    )
    return (await session.execute(stmt)).first() is not None


def add_event(session: AsyncSession, event: NotificationEvent) -> None:
    session.add(event)


async def get_event(
    session: AsyncSession, user_id: uuid.UUID, event_id: uuid.UUID
) -> NotificationEvent | None:
    stmt = select(NotificationEvent).where(
        NotificationEvent.id == event_id, NotificationEvent.user_id == user_id
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_events(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: NotificationStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[NotificationEvent]:
    stmt = (
        select(NotificationEvent)
        .where(NotificationEvent.user_id == user_id)
        .order_by(NotificationEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(NotificationEvent.status == status)
    return (await session.execute(stmt)).scalars().all()
