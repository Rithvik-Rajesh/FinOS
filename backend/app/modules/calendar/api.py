"""Financial calendar REST API."""

from __future__ import annotations

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import MoneySchema
from app.modules.calendar import service
from app.modules.calendar.schemas import CalendarResponse, FinancialEventOut

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("", response_model=CalendarResponse)
async def calendar(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    days: Annotated[int, Query(ge=1, le=366)] = 30,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> CalendarResponse:
    """Upcoming financial events for the next `days` days (daily/weekly/monthly views
    are derived client-side by grouping this ordered stream)."""
    start = clock.now()
    end = start + dt.timedelta(days=days)
    events = await service.build_events(session, user_id=user_id, start=start, end=end, clock=clock)
    outflow, inflow = service.totals(events, currency.upper())
    return CalendarResponse(
        start=start.date(),
        end=end.date(),
        events=[
            FinancialEventOut(
                type=ev.type,
                title=ev.title,
                occurs_at=ev.occurs_at,
                amount=MoneySchema.from_money(ev.amount) if ev.amount is not None else None,
                direction=ev.direction,
                source_kind=ev.source_kind,
                source_id=ev.source_id,
            )
            for ev in events
        ],
        upcoming_outflow=MoneySchema.from_money(outflow),
        upcoming_inflow=MoneySchema.from_money(inflow),
    )
