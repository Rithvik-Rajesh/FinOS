"""Building `TransactionFacts` from stored transactions.

The rules engine is pure and evaluates `TransactionFacts`. This module is the bridge:
it derives facts (including timezone-local hour/day-of-week and the human names of the
merchant and account) so both live categorization and rule simulation share one
definition of "the facts of a transaction".
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import TransactionType
from app.domain.rules import TransactionFacts
from app.modules.accounts.models import Account
from app.modules.ledger.models import Transaction
from app.modules.merchants.models import Merchant

# India-first default; per-user timezone becomes a preference in a later phase.
DEFAULT_TZ = ZoneInfo("Asia/Kolkata")


def build_facts(
    *,
    type: TransactionType,
    amount_minor: int,
    currency: str,
    occurred_at: dt.datetime,
    merchant_name: str | None,
    account_name: str | None,
    counterparty: str | None,
    note: str | None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> TransactionFacts:
    # Coerce naive timestamps (e.g. round-tripped through SQLite) to UTC before
    # converting to the user's local time, so hour/day-of-week stay correct.
    aware = occurred_at if occurred_at.tzinfo is not None else occurred_at.replace(tzinfo=dt.UTC)
    local = aware.astimezone(tz)
    return TransactionFacts(
        type=type,
        amount_minor=amount_minor,
        currency=currency,
        hour_of_day=local.hour,
        day_of_week=local.weekday(),
        merchant_name=merchant_name,
        counterparty=counterparty,
        account_name=account_name,
        note=note,
    )


@dataclass(frozen=True, slots=True)
class FactRow:
    transaction_id: uuid.UUID
    current_category_id: uuid.UUID | None
    facts: TransactionFacts


async def recent_facts(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 200,
    tz: ZoneInfo = DEFAULT_TZ,
) -> list[FactRow]:
    """Derive facts for a user's most recent transactions (for rule simulation)."""
    txn_stmt = (
        select(Transaction)
        .where(Transaction.user_id == user_id, Transaction.deleted_at.is_(None))
        .order_by(Transaction.occurred_at.desc())
        .limit(limit)
    )
    transactions = list((await session.execute(txn_stmt)).scalars().all())
    if not transactions:
        return []

    merchant_ids = {t.merchant_id for t in transactions if t.merchant_id is not None}
    account_ids = {t.account_id for t in transactions}

    merchant_names: dict[uuid.UUID, str] = {}
    if merchant_ids:
        merchant_rows = await session.execute(
            select(Merchant.id, Merchant.name).where(Merchant.id.in_(merchant_ids))
        )
        merchant_names = dict(merchant_rows.tuples())

    account_rows = await session.execute(
        select(Account.id, Account.name).where(Account.id.in_(account_ids))
    )
    account_names: dict[uuid.UUID, str] = dict(account_rows.tuples())

    result: list[FactRow] = []
    for txn in transactions:
        facts = build_facts(
            type=txn.type,
            amount_minor=txn.amount_minor,
            currency=txn.currency,
            occurred_at=txn.occurred_at,
            merchant_name=merchant_names.get(txn.merchant_id) if txn.merchant_id else None,
            account_name=account_names.get(txn.account_id),
            counterparty=txn.counterparty,
            note=txn.note,
            tz=tz,
        )
        result.append(FactRow(txn.id, txn.category_id, facts))
    return result
