"""Read transactions as pure domain `TransactionRecord`s for the reporting engine.

Keeps the transaction table owned by the ledger module: reporting consumes domain
records, never the ORM rows or the table directly.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.money import Money
from app.domain.reporting import TransactionRecord
from app.modules.ledger.models import Transaction


async def reporting_records(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
) -> list[TransactionRecord]:
    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.currency == currency.upper(),
        Transaction.deleted_at.is_(None),
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.occurred_at <= date_to)
    stmt = stmt.order_by(Transaction.occurred_at)

    rows = (await session.execute(stmt)).scalars().all()
    return [
        TransactionRecord(
            id=t.id,
            type=t.type,
            amount=Money(t.amount_minor, t.currency),
            occurred_at=t.occurred_at,
            category_id=t.category_id,
            merchant_id=t.merchant_id,
        )
        for t in rows
    ]
