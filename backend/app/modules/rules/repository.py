"""Rule data access — tenant-scoped."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.rules.models import CategorizationRule


async def get(
    session: AsyncSession, user_id: uuid.UUID, rule_id: uuid.UUID
) -> CategorizationRule | None:
    stmt = select(CategorizationRule).where(
        CategorizationRule.id == rule_id,
        CategorizationRule.user_id == user_id,
        CategorizationRule.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    active_only: bool = False,
    limit: int = 500,
    offset: int = 0,
) -> Sequence[CategorizationRule]:
    stmt = (
        select(CategorizationRule)
        .where(
            CategorizationRule.user_id == user_id,
            CategorizationRule.deleted_at.is_(None),
        )
        .order_by(CategorizationRule.priority, CategorizationRule.created_at)
        .limit(limit)
        .offset(offset)
    )
    if active_only:
        stmt = stmt.where(CategorizationRule.is_active.is_(True))
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, rule: CategorizationRule) -> None:
    session.add(rule)
