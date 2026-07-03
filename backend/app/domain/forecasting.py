"""Deterministic cash-flow forecasting.

Given a starting balance, a set of scheduled cash events (recurring inflows/outflows and
goal contributions, expanded by the caller from the recurrence engine), and an average
daily discretionary spend rate derived from history, project the balance forward day by
day. No statistics, no AI — every assumption is explicit and returned with the result
(see FORECASTING_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass

from app.domain.money import Money

_MAX_HORIZON_DAYS = 366 * 3  # guardrail


@dataclass(frozen=True, slots=True)
class CashEvent:
    """A scheduled movement of money on a date. Signed: +inflow, -outflow."""

    date: dt.date
    amount_minor: int
    label: str


@dataclass(frozen=True, slots=True)
class ForecastPoint:
    date: dt.date
    balance: Money


@dataclass(frozen=True, slots=True)
class ForecastResult:
    as_of: dt.date
    horizon_days: int
    currency: str
    starting_balance: Money
    ending_balance: Money
    min_balance: Money
    min_balance_date: dt.date
    projected_negative: bool  # does the balance dip below zero within the horizon?
    total_inflows: Money
    total_outflows: Money
    timeline: tuple[ForecastPoint, ...]  # sampled points (incl. start and end)
    assumptions: tuple[str, ...]


def forecast_cash(
    *,
    starting_balance: Money,
    events: list[CashEvent],
    daily_discretionary_minor: int,
    as_of: dt.date,
    horizon_days: int,
    sample_every_days: int = 7,
) -> ForecastResult:
    if horizon_days < 1 or horizon_days > _MAX_HORIZON_DAYS:
        raise ValueError(f"horizon_days out of range: {horizon_days}")
    if daily_discretionary_minor < 0:
        raise ValueError("daily_discretionary_minor must be >= 0")

    currency = starting_balance.currency
    by_date: dict[dt.date, int] = defaultdict(int)
    inflows = 0
    outflows = 0
    for event in events:
        by_date[event.date] += event.amount_minor
        if event.amount_minor >= 0:
            inflows += event.amount_minor
        else:
            outflows += -event.amount_minor

    balance = starting_balance.amount_minor
    min_balance = balance
    min_date = as_of
    timeline: list[ForecastPoint] = [ForecastPoint(as_of, Money(balance, currency))]

    for day in range(1, horizon_days + 1):
        current = as_of + dt.timedelta(days=day)
        balance += by_date.get(current, 0)
        balance -= daily_discretionary_minor
        outflows += daily_discretionary_minor
        if balance < min_balance:
            min_balance = balance
            min_date = current
        if day % sample_every_days == 0 or day == horizon_days:
            timeline.append(ForecastPoint(current, Money(balance, currency)))

    assumptions = (
        f"recurring events occur exactly as scheduled ({len(events)} events)",
        f"average discretionary spend of {daily_discretionary_minor} minor units/day",
        "no unplanned income or one-off expenses",
        "no interest, fees, or market movement",
    )
    return ForecastResult(
        as_of=as_of,
        horizon_days=horizon_days,
        currency=currency,
        starting_balance=starting_balance,
        ending_balance=Money(balance, currency),
        min_balance=Money(min_balance, currency),
        min_balance_date=min_date,
        projected_negative=min_balance < 0,
        total_inflows=Money(inflows, currency),
        total_outflows=Money(outflows, currency),
        timeline=tuple(timeline),
        assumptions=assumptions,
    )
