"""Recurring expenses REST API."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import MoneySchema, Page
from app.core.errors import NotFoundError
from app.domain.enums import OccurrenceStatus, RecurringStatus
from app.domain.money import Money
from app.modules.recurring import repository as repo
from app.modules.recurring import service
from app.modules.recurring.schemas import (
    DetectedPatternOut,
    DetectResponse,
    OccurrenceOut,
    SeriesCreate,
    SeriesOut,
    SeriesUpdate,
    UpcomingResponse,
)

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.post("", response_model=SeriesOut, status_code=status.HTTP_201_CREATED)
async def create_series(
    body: SeriesCreate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SeriesOut:
    series = await service.create_series(
        session, user_id=user_id, data=body, clock=clock, correlation_id=correlation_id
    )
    return SeriesOut.model_validate(series)


@router.get("", response_model=Page[SeriesOut])
async def list_series(
    session: DbSession,
    user_id: CurrentUserId,
    status_filter: Annotated[RecurringStatus | None, Query(alias="status")] = None,
    is_subscription: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SeriesOut]:
    rows = await repo.list_(
        session,
        user_id,
        status=status_filter,
        is_subscription=is_subscription,
        limit=limit,
        offset=offset,
    )
    return Page(items=[SeriesOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.post("/detect", response_model=DetectResponse)
async def detect(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> DetectResponse:
    created, patterns = await service.detect(
        session, user_id=user_id, currency=currency, clock=clock, correlation_id=correlation_id
    )
    return DetectResponse(
        created=[SeriesOut.model_validate(s) for s in created],
        patterns=[
            DetectedPatternOut(
                merchant_id=uuid.UUID(p.key),
                amount=MoneySchema(amount_minor=p.amount_minor, currency=p.currency),
                interval=p.interval,
                occurrences=p.occurrences,
                confidence=p.confidence,
                first_seen=p.first_seen,
                last_seen=p.last_seen,
                expected_next=p.expected_next,
            )
            for p in patterns
        ],
    )


@router.get("/upcoming", response_model=UpcomingResponse)
async def upcoming(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
) -> UpcomingResponse:
    now = clock.now()
    end = now + dt.timedelta(days=days)
    items: list[OccurrenceOut] = []
    for series in await repo.list_active(session, user_id):
        for due in service.occurrences_for_series(series, now, end):
            items.append(
                OccurrenceOut(
                    series_id=series.id,
                    name=series.name,
                    due_at=due,
                    amount=MoneySchema.from_money(Money(series.amount_minor, series.currency)),
                    direction=series.direction,
                    status=OccurrenceStatus.UPCOMING,
                )
            )
    items.sort(key=lambda item: item.due_at)
    return UpcomingResponse(items=items)


@router.get("/{series_id}", response_model=SeriesOut)
async def get_series(series_id: uuid.UUID, session: DbSession, user_id: CurrentUserId) -> SeriesOut:
    series = await repo.get(session, user_id, series_id)
    if series is None:
        raise NotFoundError("recurring series not found")
    return SeriesOut.model_validate(series)


@router.patch("/{series_id}", response_model=SeriesOut)
async def update_series(
    series_id: uuid.UUID,
    body: SeriesUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SeriesOut:
    series = await service.update_series(
        session,
        user_id=user_id,
        series_id=series_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return SeriesOut.model_validate(series)


@router.post("/{series_id}/approve", response_model=SeriesOut)
async def approve_series(
    series_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SeriesOut:
    series = await service.set_status(
        session,
        user_id=user_id,
        series_id=series_id,
        status=RecurringStatus.ACTIVE,
        clock=clock,
        correlation_id=correlation_id,
    )
    return SeriesOut.model_validate(series)


@router.post("/{series_id}/cancel", response_model=SeriesOut)
async def cancel_series(
    series_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SeriesOut:
    series = await service.set_status(
        session,
        user_id=user_id,
        series_id=series_id,
        status=RecurringStatus.CANCELLED,
        clock=clock,
        correlation_id=correlation_id,
    )
    return SeriesOut.model_validate(series)


@router.delete("/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_series(
    series_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_series(
        session, user_id=user_id, series_id=series_id, clock=clock, correlation_id=correlation_id
    )
