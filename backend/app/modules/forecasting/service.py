"""Forecasting orchestration.

Assembles the deterministic inputs — account balances, recurring cash flows, an observed
daily discretionary spend rate, goal projections, budget exhaustion, and subscription
costs — and runs the pure engines. Every assumption is surfaced (FORECASTING_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.domain.enums import ForecastHorizon, GoalStatus, RecurringDirection
from app.domain.forecasting import CashEvent, ForecastResult, forecast_cash
from app.domain.money import Money
from app.domain.reporting import total_spending
from app.modules.accounts import repository as accounts_repo
from app.modules.accounts import service as accounts_service
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.ledger.records import reporting_records
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring.service import occurrences_for_series
from app.modules.subscriptions import service as subscriptions_service

_DISCRETIONARY_LOOKBACK_DAYS = 90


@dataclass(frozen=True, slots=True)
class GoalCompletion:
    goal_id: uuid.UUID
    name: str
    projected_completion: dt.date | None


@dataclass(frozen=True, slots=True)
class BudgetExhaustion:
    budget_id: uuid.UUID
    name: str
    projected_exhaustion: dt.date | None


@dataclass(frozen=True, slots=True)
class ForecastBundle:
    cash: ForecastResult
    daily_discretionary_minor: int
    goal_completions: tuple[GoalCompletion, ...]
    budget_exhaustions: tuple[BudgetExhaustion, ...]
    subscription_monthly: Money
    subscription_annual: Money


async def _starting_balance(session: AsyncSession, user_id: uuid.UUID, currency: str) -> int:
    total = 0
    for account in await accounts_repo.list_(session, user_id, limit=1000):
        if account.currency != currency:
            continue
        balance = await accounts_service.get_balance(session, user_id=user_id, account=account)
        total += balance.amount_minor
    return total


async def _recurring_events(
    session: AsyncSession, user_id: uuid.UUID, currency: str, start: dt.datetime, end: dt.datetime
) -> list[CashEvent]:
    events: list[CashEvent] = []
    for series in await recurring_repo.list_active(session, user_id):
        if series.currency != currency:
            continue
        signed = (
            series.amount_minor
            if series.direction is RecurringDirection.INFLOW
            else -series.amount_minor
        )
        for due in occurrences_for_series(series, start, end):
            events.append(CashEvent(due.date(), signed, series.name))
    return events


async def _daily_discretionary(
    session: AsyncSession, user_id: uuid.UUID, currency: str, now: dt.datetime
) -> int:
    since = now - dt.timedelta(days=_DISCRETIONARY_LOOKBACK_DAYS)
    records = await reporting_records(
        session, user_id, currency=currency, date_from=since, date_to=now
    )
    spent = total_spending(records, currency).amount_minor
    return max(0, spent // _DISCRETIONARY_LOOKBACK_DAYS)


async def build_forecast(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    currency: str,
    horizon: ForecastHorizon,
    clock: Clock,
) -> ForecastBundle:
    currency = currency.upper()
    now = clock.now()
    as_of = now.date()
    end = now + dt.timedelta(days=horizon.days)

    starting = Money(await _starting_balance(session, user_id, currency), currency)
    events = await _recurring_events(session, user_id, currency, now, end)
    daily_disc = await _daily_discretionary(session, user_id, currency, now)

    cash = forecast_cash(
        starting_balance=starting,
        events=events,
        daily_discretionary_minor=daily_disc,
        as_of=as_of,
        horizon_days=horizon.days,
    )

    goal_completions: list[GoalCompletion] = []
    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=1000):
        if goal.currency != currency:
            continue
        projection, _ = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        goal_completions.append(GoalCompletion(goal.id, goal.name, projection.projected_completion))

    budget_exhaustions: list[BudgetExhaustion] = []
    for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=1000):
        if budget.currency != currency:
            continue
        status = await budgets_service.get_status(
            session, user_id=user_id, budget=budget, as_of=as_of
        )
        earliest = [line.projected_exhaustion for line in status.lines if line.projected_exhaustion]
        budget_exhaustions.append(
            BudgetExhaustion(budget.id, budget.name, min(earliest) if earliest else None)
        )

    cost, _ = await subscriptions_service.summary(session, user_id=user_id, currency=currency)

    return ForecastBundle(
        cash=cash,
        daily_discretionary_minor=daily_disc,
        goal_completions=tuple(goal_completions),
        budget_exhaustions=tuple(budget_exhaustions),
        subscription_monthly=cost.monthly,
        subscription_annual=cost.annual,
    )
