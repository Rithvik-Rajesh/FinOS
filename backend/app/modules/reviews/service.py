"""Review generation — assembles a deterministic snapshot and persists it.

Every number comes from an existing engine; nothing here invents figures. Snapshots are
idempotent per (period, period_start) so re-generating refreshes rather than duplicates.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.domain.enums import GoalStatus, ReviewPeriod
from app.domain.goals import add_months
from app.domain.ids import new_id
from app.domain.reporting import (
    TransactionRecord,
    spending_by_category,
    total_income,
    total_spending,
)
from app.domain.reviews import savings_rate
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.categories import repository as categories_repo
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.ledger.facts import DEFAULT_TZ
from app.modules.ledger.records import reporting_records
from app.modules.reviews import repository as repo
from app.modules.reviews.models import Review
from app.modules.subscriptions import service as subscriptions_service


def period_bounds(period: ReviewPeriod, as_of: dt.date, offset: int) -> tuple[dt.date, dt.date]:
    if period is ReviewPeriod.WEEKLY:
        monday = as_of - dt.timedelta(days=as_of.weekday())
        start = monday + dt.timedelta(days=7 * offset)
        return start, start + dt.timedelta(days=6)
    if period is ReviewPeriod.MONTHLY:
        base = add_months(dt.date(as_of.year, as_of.month, 1), offset)
        return base, add_months(base, 1) - dt.timedelta(days=1)
    quarter_start_month = ((as_of.month - 1) // 3) * 3 + 1
    base = add_months(dt.date(as_of.year, quarter_start_month, 1), offset * 3)
    return base, add_months(base, 3) - dt.timedelta(days=1)


def _range(start: dt.date, end: dt.date) -> tuple[dt.datetime, dt.datetime]:
    return (
        dt.datetime.combine(start, dt.time.min, tzinfo=DEFAULT_TZ),
        dt.datetime.combine(end, dt.time.max, tzinfo=DEFAULT_TZ),
    )


async def generate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    period: ReviewPeriod,
    currency: str,
    clock: Clock,
    offset: int = 0,
) -> Review:
    currency = currency.upper()
    as_of = clock.now().date()
    start, end = period_bounds(period, as_of, offset)
    prev_start, prev_end = period_bounds(period, as_of, offset - 1)

    cur_from, cur_to = _range(start, end)
    prev_from, prev_to = _range(prev_start, prev_end)
    cur = await reporting_records(
        session, user_id, currency=currency, date_from=cur_from, date_to=cur_to
    )
    prev = await reporting_records(
        session, user_id, currency=currency, date_from=prev_from, date_to=prev_to
    )

    spent = total_spending(cur, currency)
    income = total_income(cur, currency)
    net = income - spent
    rate = savings_rate(income=income, spending=spent)

    largest = await _largest_category_increase(session, user_id, currency, cur, prev)
    goal_progress = await _goal_progress(session, user_id, currency, clock)
    budget_performance = await _budget_performance(session, user_id, currency, as_of)
    cost, sub_count = await subscriptions_service.summary(
        session, user_id=user_id, currency=currency
    )

    payload: dict[str, Any] = {
        "largest_category_increase": largest,
        "goal_progress": goal_progress,
        "budget_performance": budget_performance,
        "subscription_monthly_minor": cost.monthly.amount_minor,
        "subscription_count": sub_count,
    }

    review = await repo.get_for_period(session, user_id, period, start)
    if review is None:
        review = Review(id=new_id(), user_id=user_id, period=period, period_start=start)
        repo.add(session, review)
    review.period_end = end
    review.currency = currency
    review.total_spent_minor = spent.amount_minor
    review.total_income_minor = income.amount_minor
    review.net_cashflow_minor = net.amount_minor
    review.savings_rate_bps = int(rate * 100) if rate is not None else None
    review.payload = payload
    review.generated_at = clock.now()
    await session.flush()
    return review


async def _largest_category_increase(
    session: AsyncSession,
    user_id: uuid.UUID,
    currency: str,
    cur: list[TransactionRecord],
    prev: list[TransactionRecord],
) -> dict[str, Any] | None:
    cur_by = {g.key: g.total.amount_minor for g in spending_by_category(cur, currency)}
    prev_by = {g.key: g.total.amount_minor for g in spending_by_category(prev, currency)}
    best_id: uuid.UUID | None = None
    best_delta = 0
    for cid, amount in cur_by.items():
        if cid is None:
            continue
        delta = amount - prev_by.get(cid, 0)
        if delta > best_delta:
            best_id, best_delta = cid, delta
    if best_id is None:
        return None
    category = await categories_repo.get(session, user_id, best_id)
    return {
        "category_id": str(best_id),
        "name": category.name if category is not None else None,
        "delta_minor": best_delta,
    }


async def _goal_progress(
    session: AsyncSession, user_id: uuid.UUID, currency: str, clock: Clock
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=100):
        if goal.currency != currency:
            continue
        projection, _ = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        result.append(
            {
                "goal_id": str(goal.id),
                "name": goal.name,
                "progress_ratio": projection.progress_ratio,
                "health": projection.health.value,
            }
        )
    return result


async def _budget_performance(
    session: AsyncSession, user_id: uuid.UUID, currency: str, as_of: dt.date
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=100):
        if budget.currency != currency:
            continue
        status = await budgets_service.get_status(
            session, user_id=user_id, budget=budget, as_of=as_of
        )
        result.append(
            {
                "budget_id": str(budget.id),
                "name": budget.name,
                "utilization_ratio": status.utilization_ratio,
                "health": status.health.value,
                "spent_minor": status.total_spent.amount_minor,
                "allocated_minor": status.total_allocated.amount_minor,
            }
        )
    return result