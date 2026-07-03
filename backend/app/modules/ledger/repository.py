"""Transaction & ledger-entry data access — tenant-scoped.

The ledger list supports filtering, sorting, and keyset (cursor) pagination over the two
stable sort keys used by the app: `occurred_at` and `amount`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any, Literal

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TransactionStatus, TransactionType
from app.modules.ledger.models import LedgerEntry, Transaction

SortField = Literal["occurred_at", "amount"]
SortOrder = Literal["asc", "desc"]


async def get(
    session: AsyncSession,
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Transaction | None:
    stmt = select(Transaction).where(Transaction.id == txn_id, Transaction.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Transaction.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


def add(session: AsyncSession, txn: Transaction) -> None:
    session.add(txn)


def add_entries(session: AsyncSession, entries: Sequence[LedgerEntry]) -> None:
    session.add_all(entries)


async def entries_for(
    session: AsyncSession, user_id: uuid.UUID, txn_id: uuid.UUID
) -> Sequence[LedgerEntry]:
    stmt = select(LedgerEntry).where(
        LedgerEntry.user_id == user_id, LedgerEntry.transaction_id == txn_id
    )
    return (await session.execute(stmt)).scalars().all()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: dt.datetime | None = None,
    date_to: dt.datetime | None = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    type_: TransactionType | None = None,
    status: TransactionStatus | None = None,
    sort: SortField = "occurred_at",
    order: SortOrder = "desc",
    cursor: dict[str, Any] | None = None,
    limit: int = 50,
) -> tuple[list[Transaction], bool]:
    """Return (rows, has_more). Fetches limit+1 to detect a further page."""
    stmt = select(Transaction).where(
        Transaction.user_id == user_id, Transaction.deleted_at.is_(None)
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.occurred_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.occurred_at <= date_to)
    if account_id is not None:
        stmt = stmt.where(Transaction.account_id == account_id)
    if category_id is not None:
        stmt = stmt.where(Transaction.category_id == category_id)
    if merchant_id is not None:
        stmt = stmt.where(Transaction.merchant_id == merchant_id)
    if type_ is not None:
        stmt = stmt.where(Transaction.type == type_)
    if status is not None:
        stmt = stmt.where(Transaction.status == status)

    sort_col = Transaction.occurred_at if sort == "occurred_at" else Transaction.amount_minor

    if cursor is not None:
        key = _parse_key(sort, cursor["k"])
        last_id = uuid.UUID(cursor["id"])
        if order == "desc":
            stmt = stmt.where(or_(sort_col < key, and_(sort_col == key, Transaction.id < last_id)))
        else:
            stmt = stmt.where(or_(sort_col > key, and_(sort_col == key, Transaction.id > last_id)))

    direction = sort_col.desc() if order == "desc" else sort_col.asc()
    id_dir = Transaction.id.desc() if order == "desc" else Transaction.id.asc()
    stmt = stmt.order_by(direction, id_dir).limit(limit + 1)

    rows = list((await session.execute(stmt)).scalars().all())
    has_more = len(rows) > limit
    return rows[:limit], has_more


def _parse_key(sort: SortField, raw: Any) -> Any:
    if sort == "amount":
        return int(raw)
    return dt.datetime.fromisoformat(str(raw))
