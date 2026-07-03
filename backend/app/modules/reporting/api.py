"""Reporting REST API — deterministic spending analytics (no AI)."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import MoneySchema
from app.domain.enums import Period
from app.modules.reporting import service
from app.modules.reporting.schemas import (
    GroupTotalOut,
    GrowthOut,
    PeriodTotalOut,
    SummaryOut,
)

router = APIRouter(prefix="/reports", tags=["reports"])

Currency = Annotated[str, Query(min_length=3, max_length=3)]


@router.get("/spending", response_model=list[GroupTotalOut])
async def spending(
    session: DbSession,
    user_id: CurrentUserId,
    group_by: Literal["category", "merchant"] = "category",
    currency: Currency = "INR",
    date_from: Annotated[dt.datetime | None, Query(alias="from")] = None,
    date_to: Annotated[dt.datetime | None, Query(alias="to")] = None,
) -> list[GroupTotalOut]:
    groups = await service.spending_by(
        session,
        user_id,
        group_by=group_by,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    return [
        GroupTotalOut(key=g.key, total=MoneySchema.from_money(g.total), count=g.count)
        for g in groups
    ]


@router.get("/timeseries", response_model=list[PeriodTotalOut])
async def timeseries(
    session: DbSession,
    user_id: CurrentUserId,
    period: Period = Period.MONTH,
    currency: Currency = "INR",
    date_from: Annotated[dt.datetime | None, Query(alias="from")] = None,
    date_to: Annotated[dt.datetime | None, Query(alias="to")] = None,
) -> list[PeriodTotalOut]:
    buckets = await service.timeseries(
        session,
        user_id,
        period=period,
        currency=currency,
        date_from=date_from,
        date_to=date_to,
    )
    return [
        PeriodTotalOut(
            period_start=b.period_start, total=MoneySchema.from_money(b.total), count=b.count
        )
        for b in buckets
    ]


@router.get("/summary", response_model=SummaryOut)
async def summary(
    session: DbSession,
    user_id: CurrentUserId,
    currency: Currency = "INR",
    date_from: Annotated[dt.datetime | None, Query(alias="from")] = None,
    date_to: Annotated[dt.datetime | None, Query(alias="to")] = None,
) -> SummaryOut:
    spending_total, income, net = await service.summary(
        session, user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    return SummaryOut(
        currency=currency.upper(),
        spending=MoneySchema.from_money(spending_total),
        income=MoneySchema.from_money(income),
        net=MoneySchema.from_money(net),
    )


@router.get("/growth", response_model=GrowthOut)
async def growth(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    window: Literal["wow", "mom", "yoy"] = "mom",
    currency: Currency = "INR",
    as_of: dt.datetime | None = None,
) -> GrowthOut:
    result = await service.spending_growth(
        session,
        user_id,
        window=window,
        currency=currency,
        as_of=as_of or clock.now(),
    )
    return GrowthOut(
        current=MoneySchema.from_money(result.current),
        previous=MoneySchema.from_money(result.previous),
        delta=MoneySchema.from_money(result.delta),
        pct_change=result.pct_change,
        is_new=result.is_new,
    )
