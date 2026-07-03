"""Subscriptions REST API (views + analytics over recurring series)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import MoneySchema, Page
from app.domain.enums import RecurringStatus
from app.domain.money import Money
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring import service as recurring_service
from app.modules.recurring.schemas import SeriesOut
from app.modules.subscriptions import service
from app.modules.subscriptions.schemas import (
    InactiveResponse,
    InactiveSubscriptionOut,
    RenewalOut,
    RenewalsResponse,
    SubscriptionSummaryOut,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("", response_model=Page[SeriesOut])
async def list_subscriptions(
    session: DbSession,
    user_id: CurrentUserId,
    status_filter: Annotated[RecurringStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[SeriesOut]:
    rows = await recurring_repo.list_(
        session, user_id, status=status_filter, is_subscription=True, limit=limit, offset=offset
    )
    return Page(items=[SeriesOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.get("/summary", response_model=SubscriptionSummaryOut)
async def summary(
    session: DbSession,
    user_id: CurrentUserId,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> SubscriptionSummaryOut:
    cost, count = await service.summary(session, user_id=user_id, currency=currency)
    return SubscriptionSummaryOut(
        currency=currency.upper(),
        active_count=count,
        monthly=MoneySchema.from_money(cost.monthly),
        annual=MoneySchema.from_money(cost.annual),
    )


@router.get("/inactive", response_model=InactiveResponse)
async def inactive(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    days: Annotated[int, Query(ge=1, le=365)] = 60,
) -> InactiveResponse:
    rows = await service.inactive(session, user_id=user_id, clock=clock, inactive_days=days)
    return InactiveResponse(
        items=[
            InactiveSubscriptionOut(
                series_id=i.series.id,
                name=i.series.name,
                last_seen=i.last_seen,
                days_inactive=i.days_inactive,
            )
            for i in rows
        ]
    )


@router.get("/renewals", response_model=RenewalsResponse)
async def renewals(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    within_days: Annotated[int, Query(ge=1, le=366)] = 30,
) -> RenewalsResponse:
    rows = await service.upcoming_renewals(
        session, user_id=user_id, within_days=within_days, clock=clock
    )
    return RenewalsResponse(
        items=[
            RenewalOut(
                series_id=s.id,
                name=s.name,
                next_due_at=s.next_due_at,
                amount=MoneySchema.from_money(Money(s.amount_minor, s.currency)),
            )
            for s in rows
        ]
    )


@router.post("/{series_id}/cancel", response_model=SeriesOut, status_code=status.HTTP_200_OK)
async def cancel(
    series_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SeriesOut:
    series = await recurring_service.set_status(
        session,
        user_id=user_id,
        series_id=series_id,
        status=RecurringStatus.CANCELLED,
        clock=clock,
        correlation_id=correlation_id,
    )
    return SeriesOut.model_validate(series)
