"""Small ledger read helpers for other modules (keeps the transactions table owned here)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ledger.models import Transaction


async def merchant_last_seen(
    session: AsyncSession, user_id: uuid.UUID, merchant_id: uuid.UUID
) -> dt.datetime | None:
    """The most recent transaction time for a merchant, or None (used for inactivity)."""
    stmt = select(func.max(Transaction.occurred_at)).where(
        Transaction.user_id == user_id,
        Transaction.merchant_id == merchant_id,
        Transaction.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()
