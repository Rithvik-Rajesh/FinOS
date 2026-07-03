"""Reporting use cases.

Loads transactions as pure domain records and delegates every calculation to
`app.domain.reporting` (deterministic, no AI). Growth compares a period-to-date against
the equivalent to-date window in the prior period, so mid-period comparisons are fair.
"""

from __future__ import annotations

import calendar
import datetime as dt
import uuid
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import reporting as calc
from app.domain.enums import Period
from app.domain.money import Money
from app.domain.reporting import GroupTotal, GrowthResult, PeriodTotal
from app.modules.ledger.facts import DEFAULT_TZ
from app.modules.ledger.records import reporting_records

GrowthWindow = Literal["wow", "mom", "yoy"]


async def spending_by(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    group_by: Literal["category", "merchant"],
    currency: str,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
) -> list[GroupTotal]:
    records = await reporting_records(
        session, user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    if group_by == "category":
        return calc.spending_by_category(records, currency)
    return calc.spending_by_merchant(records, currency)


async def timeseries(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    period: Period,
    currency: str,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
    tz: ZoneInfo = DEFAULT_TZ,
) -> list[PeriodTotal]:
    records = await reporting_records(
        session, user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    return calc.totals_by_period(records, currency, period, tz)


async def summary(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    currency: str,
    date_from: dt.datetime | None,
    date_to: dt.datetime | None,
) -> tuple[Money, Money, Money]:
    records = await reporting_records(
        session, user_id, currency=currency, date_from=date_from, date_to=date_to
    )
    spending = calc.total_spending(records, currency)
    income = calc.total_income(records, currency)
    return spending, income, income - spending


def _add_months(d: dt.date, months: int) -> dt.date:
    index = d.month - 1 + months
    year = d.year + index // 12
    month = index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def _growth_windows(
    window: GrowthWindow, as_of_local: dt.datetime, tz: ZoneInfo
) -> tuple[tuple[dt.datetime, dt.datetime], tuple[dt.datetime, dt.datetime]]:
    today = as_of_local.date()
    if window == "wow":
        cur_start_d = today - dt.timedelta(days=today.weekday())
        prev_start_d = cur_start_d - dt.timedelta(days=7)
    elif window == "mom":
        cur_start_d = today.replace(day=1)
        prev_start_d = _add_months(cur_start_d, -1)
    else:  # yoy
        cur_start_d = today.replace(day=1)
        prev_start_d = cur_start_d.replace(year=cur_start_d.year - 1)

    cur_start = dt.datetime.combine(cur_start_d, dt.time.min, tzinfo=tz)
    prev_start = dt.datetime.combine(prev_start_d, dt.time.min, tzinfo=tz)
    elapsed = as_of_local - cur_start
    return (cur_start, as_of_local), (prev_start, prev_start + elapsed)


async def spending_growth(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    window: GrowthWindow,
    currency: str,
    as_of: dt.datetime,
    tz: ZoneInfo = DEFAULT_TZ,
) -> GrowthResult:
    as_of_local = as_of.astimezone(tz)
    (cur_start, cur_end), (prev_start, prev_end) = _growth_windows(window, as_of_local, tz)

    current_records = await reporting_records(
        session, user_id, currency=currency, date_from=cur_start, date_to=cur_end
    )
    previous_records = await reporting_records(
        session, user_id, currency=currency, date_from=prev_start, date_to=prev_end
    )
    return calc.growth(
        calc.total_spending(current_records, currency),
        calc.total_spending(previous_records, currency),
    )
