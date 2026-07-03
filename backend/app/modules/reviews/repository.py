"""Review snapshot data access."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ReviewPeriod
from app.modules.reviews.models import Review


async def get(session: AsyncSession, user_id: uuid.UUID, review_id: uuid.UUID) -> Review | None:
    stmt = select(Review).where(Review.id == review_id, Review.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_for_period(
    session: AsyncSession, user_id: uuid.UUID, period: ReviewPeriod, period_start: dt.date
) -> Review | None:
    stmt = select(Review).where(
        Review.user_id == user_id, Review.period == period, Review.period_start == period_start
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    period: ReviewPeriod | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[Review]:
    stmt = (
        select(Review)
        .where(Review.user_id == user_id)
        .order_by(Review.period_start.desc())
        .limit(limit)
        .offset(offset)
    )
    if period is not None:
        stmt = stmt.where(Review.period == period)
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, review: Review) -> None:
    session.add(review)
