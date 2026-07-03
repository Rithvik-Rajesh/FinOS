"""Account balance queries derived from the immutable ledger entries.

Balance == account opening balance + sum of that account's entries. Because edits and
deletes append reversing entries, this sum is always exact without filtering.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.money import Money
from app.modules.ledger.models import LedgerEntry


async def entries_sum(session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(LedgerEntry.amount_minor), 0)).where(
        LedgerEntry.user_id == user_id, LedgerEntry.account_id == account_id
    )
    return int((await session.execute(stmt)).scalar_one())


async def account_balance(
    session: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    opening_minor: int,
    currency: str,
) -> Money:
    total = opening_minor + await entries_sum(session, user_id, account_id)
    return Money(total, currency)
