"""Account data access. The only place that touches the accounts table.

Every query is scoped to the authenticated `user_id` — this is the primary
object-level authorization control (SECURITY.md#authorization).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounts.models import Account


async def get(
    session: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    *,
    include_deleted: bool = False,
) -> Account | None:
    stmt = select(Account).where(Account.id == account_id, Account.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(Account.deleted_at.is_(None))
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    include_archived: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Account]:
    stmt = (
        select(Account)
        .where(Account.user_id == user_id, Account.deleted_at.is_(None))
        .order_by(Account.created_at)
        .limit(limit)
        .offset(offset)
    )
    if not include_archived:
        stmt = stmt.where(Account.is_archived.is_(False))
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, account: Account) -> None:
    session.add(account)
