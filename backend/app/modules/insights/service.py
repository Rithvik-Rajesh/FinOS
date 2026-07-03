"""Insight orchestration — assembles facts from every engine and runs the pure generators.

Deterministic and explainable. Insights are computed on read (ADR-011); the AI copilot
consumes them but never recomputes them.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain import insights as gen
from app.domain.clock import Clock
from app.domain.enums import BudgetHealth, ForecastHorizon, GoalStatus
from app.domain.goals import add_months
from app.domain.insights import Insight
from app.domain.money import Money
from app.domain.reporting import growth, spending_by_merchant, total_spending
from app.domain.simulation import GoalSimInput, analyze_goal_impact
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.forecasting import service as forecasting_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.ledger.facts import DEFAULT_TZ
from app.modules.ledger.records import reporting_records
from app.modules.merchants import repository as merchants_repo
from app.modules.subscriptions import service as subscriptions_service

_INACTIVE_DAYS = 60


def _month_windows(
    now: dt.datetime,
) -> tuple[tuple[dt.datetime, dt.datetime], tuple[dt.datetime, dt.datetime]]:
    local = now.astimezone(DEFAULT_TZ)
    cur_start_d = local.date().replace(day=1)
    prev_start_d = add_months(cur_start_d, -1)
    cur_start = dt.datetime.combine(cur_start_d, dt.time.min, tzinfo=DEFAULT_TZ)
    prev_start = dt.datetime.combine(prev_start_d, dt.time.min, tzinfo=DEFAULT_TZ)
    elapsed = now - cur_start
    return (cur_start, now), (prev_start, prev_start + elapsed)


async def _spending_insight(
    session: AsyncSession, user_id: uuid.UUID, currency: str, now: dt.datetime, clock: Clock
) -> Insight | None:
    (cur_start, cur_end), (prev_start, prev_end) = _month_windows(now)
    cur = await reporting_records(
        session, user_id, currency=currency, date_from=cur_start, date_to=cur_end
    )
    prev = await reporting_records(
        session, user_id, currency=currency, date_from=prev_start, date_to=prev_end
    )
    cur_total = total_spending(cur, currency)
    prev_total = total_spending(prev, currency)
    change = growth(cur_total, prev_total)
    if change.pct_change is None or change.pct_change <= 0:
        return None

    # Top merchant driver by positive delta.
    cur_by_m = {g.key: g.total.amount_minor for g in spending_by_merchant(cur, currency)}
    prev_by_m = {g.key: g.total.amount_minor for g in spending_by_merchant(prev, currency)}
    best_id: uuid.UUID | None = None
    best_delta = 0
    for mid, amount in cur_by_m.items():
        if mid is None:
            continue
        delta = amount - prev_by_m.get(mid, 0)
        if delta > best_delta:
            best_id, best_delta = mid, delta
    driver_name = None
    if best_id is not None:
        merchant = await merchants_repo.get(session, user_id, best_id)
        driver_name = merchant.name if merchant is not None else None

    # Goal impact of the extra spend on the highest-priority active goal.
    goal_name: str | None = None
    goal_delay: int | None = None
    extra = cur_total.amount_minor - prev_total.amount_minor
    goals = await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=1)
    if goals and extra > 0:
        goal = goals[0]
        if goal.currency == currency:
            projection, current = await goals_service.get_projection(
                session, user_id=user_id, goal=goal, clock=clock
            )
            impact = analyze_goal_impact(
                GoalSimInput(
                    goal_id=goal.id,
                    name=goal.name,
                    target=projection.target,
                    current=current,
                    deadline=goal.deadline,
                    observed_monthly=projection.observed_monthly,
                ),
                reduce_current_by=Money(extra, currency),
                as_of=now.date(),
            )
            goal_name, goal_delay = goal.name, impact.delay_months

    return gen.spending_insight(
        current=cur_total,
        previous=prev_total,
        change_pct=change.pct_change,
        driver_name=driver_name,
        driver_delta=Money(best_delta, currency) if best_id else None,
        goal_name=goal_name,
        goal_delay_months=goal_delay,
    )


async def generate(
    session: AsyncSession, *, user_id: uuid.UUID, currency: str, clock: Clock
) -> list[Insight]:
    currency = currency.upper()
    now = clock.now()
    insights: list[Insight] = []

    spending = await _spending_insight(session, user_id, currency, now, clock)
    if spending is not None:
        insights.append(spending)

    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=100):
        if goal.currency != currency:
            continue
        projection, _ = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        item = gen.goal_insight(
            goal_id=goal.id,
            goal_name=goal.name,
            health=projection.health,
            required_monthly=projection.required_monthly,
        )
        if item is not None:
            insights.append(item)

    for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=100):
        if budget.currency != currency:
            continue
        status = await budgets_service.get_status(
            session, user_id=user_id, budget=budget, as_of=now.date()
        )
        item = gen.budget_insight(
            budget_id=budget.id,
            budget_name=budget.name,
            is_over=status.health is BudgetHealth.OVER,
            is_warning=status.health is BudgetHealth.WARNING,
            remaining=status.total_remaining,
        )
        if item is not None:
            insights.append(item)

    inactive = await subscriptions_service.inactive(
        session, user_id=user_id, clock=clock, inactive_days=_INACTIVE_DAYS
    )
    cost, _ = await subscriptions_service.summary(session, user_id=user_id, currency=currency)
    sub = gen.subscription_insight(inactive_count=len(inactive), monthly_cost=cost.monthly)
    if sub is not None:
        insights.append(sub)

    bundle = await forecasting_service.build_forecast(
        session, user_id=user_id, currency=currency, horizon=ForecastHorizon.D30, clock=clock
    )
    fc = gen.forecast_insight(
        projected_negative=bundle.cash.projected_negative,
        min_balance=bundle.cash.min_balance,
        min_balance_date_iso=bundle.cash.min_balance_date.isoformat(),
    )
    if fc is not None:
        insights.append(fc)

    return gen.rank(insights)
