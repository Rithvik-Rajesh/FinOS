"""Recurring series data access — tenant-scoped."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RecurringStatus
from app.modules.recurring.models import RecurringSeries


async def get(
    session: AsyncSession, user_id: uuid.UUID, series_id: uuid.UUID
) -> RecurringSeries | None:
    stmt = select(RecurringSeries).where(
        RecurringSeries.id == series_id,
        RecurringSeries.user_id == user_id,
        RecurringSeries.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: RecurringStatus | None = None,
    is_subscription: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[RecurringSeries]:
    stmt = (
        select(RecurringSeries)
        .where(RecurringSeries.user_id == user_id, RecurringSeries.deleted_at.is_(None))
        .order_by(RecurringSeries.next_due_at)
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(RecurringSeries.status == status)
    if is_subscription is not None:
        stmt = stmt.where(RecurringSeries.is_subscription.is_(is_subscription))
    return (await session.execute(stmt)).scalars().all()


async def list_active(session: AsyncSession, user_id: uuid.UUID) -> Sequence[RecurringSeries]:
    return await list_(session, user_id, status=RecurringStatus.ACTIVE, limit=1000)


async def exists_similar(
    session: AsyncSession, user_id: uuid.UUID, merchant_id: uuid.UUID, amount_minor: int
) -> bool:
    """Is there already a (non-deleted) series for this merchant + amount?"""
    stmt = select(RecurringSeries.id).where(
        RecurringSeries.user_id == user_id,
        RecurringSeries.merchant_id == merchant_id,
        RecurringSeries.amount_minor == amount_minor,
        RecurringSeries.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).first() is not None


def add(session: AsyncSession, series: RecurringSeries) -> None:
    session.add(series)
