"""Category data access — tenant-scoped."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.categories.models import Category


async def get(session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID) -> Category | None:
    stmt = select(Category).where(
        Category.id == category_id,
        Category.user_id == user_id,
        Category.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    parent_id: uuid.UUID | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Category]:
    stmt = (
        select(Category)
        .where(Category.user_id == user_id, Category.deleted_at.is_(None))
        .order_by(Category.name)
        .limit(limit)
        .offset(offset)
    )
    if parent_id is not None:
        stmt = stmt.where(Category.parent_id == parent_id)
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, category: Category) -> None:
    session.add(category)
