"""Reviews REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import Page
from app.core.errors import NotFoundError
from app.domain.enums import ReviewPeriod
from app.modules.reviews import repository as repo
from app.modules.reviews import service
from app.modules.reviews.schemas import ReviewOut

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/generate", response_model=ReviewOut)
async def generate(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    period: ReviewPeriod = ReviewPeriod.WEEKLY,
    offset: Annotated[int, Query(ge=-52, le=0)] = 0,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> ReviewOut:
    """Generate (or refresh) the review snapshot for a period; idempotent per period."""
    review = await service.generate(
        session, user_id=user_id, period=period, currency=currency, clock=clock, offset=offset
    )
    return ReviewOut.from_model(review)


@router.get("", response_model=Page[ReviewOut])
async def list_reviews(
    session: DbSession,
    user_id: CurrentUserId,
    period: ReviewPeriod | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ReviewOut]:
    rows = await repo.list_(session, user_id, period=period, limit=limit, offset=offset)
    return Page(items=[ReviewOut.from_model(r) for r in rows], has_more=len(rows) == limit)


@router.get("/{review_id}", response_model=ReviewOut)
async def get_review(review_id: uuid.UUID, session: DbSession, user_id: CurrentUserId) -> ReviewOut:
    review = await repo.get(session, user_id, review_id)
    if review is None:
        raise NotFoundError("review not found")
    return ReviewOut.from_model(review)
