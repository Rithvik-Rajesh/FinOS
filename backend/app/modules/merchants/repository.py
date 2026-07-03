"""Merchant data access — tenant-scoped."""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.merchants.models import Merchant


async def get(session: AsyncSession, user_id: uuid.UUID, merchant_id: uuid.UUID) -> Merchant | None:
    stmt = select(Merchant).where(
        Merchant.id == merchant_id,
        Merchant.user_id == user_id,
        Merchant.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def find_by_normalized(
    session: AsyncSession, user_id: uuid.UUID, normalized_name: str
) -> Merchant | None:
    stmt = select(Merchant).where(
        Merchant.user_id == user_id,
        Merchant.normalized_name == normalized_name,
        Merchant.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalars().first()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    query: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> Sequence[Merchant]:
    stmt = (
        select(Merchant)
        .where(Merchant.user_id == user_id, Merchant.deleted_at.is_(None))
        .order_by(Merchant.name)
        .limit(limit)
        .offset(offset)
    )
    if query:
        stmt = stmt.where(Merchant.normalized_name.contains(query.casefold()))
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, merchant: Merchant) -> None:
    session.add(merchant)
