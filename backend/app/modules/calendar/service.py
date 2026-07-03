"""Financial calendar — deterministic aggregation of future obligations.

Composes upcoming recurring occurrences, goal deadlines, and budget period checkpoints
into a single ordered stream of `FinancialEvent`s. Nothing is stored; the calendar always
reflects current definitions (ADR-011).
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.domain.enums import (
    FinancialEventType,
    GoalStatus,
    RecurringDirection,
    RecurringKind,
)
from app.domain.money import Money
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.goals import repository as goals_repo
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring.models import RecurringSeries
from app.modules.recurring.service import occurrences_for_series

_MAX_PERIOD_SCAN = 60


@dataclass(frozen=True, slots=True)
class FinancialEvent:
    type: FinancialEventType
    title: str
    occurs_at: dt.datetime
    amount: Money | None
    direction: str  # inflow | outflow | neutral
    source_kind: str
    source_id: uuid.UUID | None


def _event_type(series: RecurringSeries) -> FinancialEventType:
    if series.is_subscription:
        return FinancialEventType.SUBSCRIPTION
    match series.kind:
        case RecurringKind.RENT | RecurringKind.UTILITY:
            return FinancialEventType.BILL
        case RecurringKind.EMI:
            return FinancialEventType.EMI
        case RecurringKind.SALARY:
            return FinancialEventType.SALARY
        case _:
            return FinancialEventType.RECURRING_EXPENSE


async def build_events(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    start: dt.datetime,
    end: dt.datetime,
    clock: Clock,
) -> list[FinancialEvent]:
    events: list[FinancialEvent] = []

    for series in await recurring_repo.list_active(session, user_id):
        for due in occurrences_for_series(series, start, end):
            events.append(
                FinancialEvent(
                    type=_event_type(series),
                    title=series.name,
                    occurs_at=due,
                    amount=Money(series.amount_minor, series.currency),
                    direction=series.direction.value,
                    source_kind="recurring_series",
                    source_id=series.id,
                )
            )

    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=1000):
        if goal.deadline is not None and start.date() <= goal.deadline <= end.date():
            events.append(
                FinancialEvent(
                    type=FinancialEventType.GOAL_MILESTONE,
                    title=goal.name,
                    occurs_at=dt.datetime.combine(goal.deadline, dt.time(9, 0), tzinfo=dt.UTC),
                    amount=Money(goal.target_amount_minor, goal.currency),
                    direction="neutral",
                    source_kind="goal",
                    source_id=goal.id,
                )
            )

    for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=1000):
        for offset in range(0, _MAX_PERIOD_SCAN):
            period_start, period_end = budgets_service.period_bounds(
                budget, clock.now().date(), offset
            )
            if period_start > end.date():
                break
            if start.date() <= period_end <= end.date():
                events.append(
                    FinancialEvent(
                        type=FinancialEventType.BUDGET_CHECKPOINT,
                        title=f"{budget.name} period ends",
                        occurs_at=dt.datetime.combine(period_end, dt.time(23, 59), tzinfo=dt.UTC),
                        amount=None,
                        direction="neutral",
                        source_kind="budget",
                        source_id=budget.id,
                    )
                )

    events.sort(key=lambda ev: ev.occurs_at)
    return events


def totals(events: list[FinancialEvent], currency: str) -> tuple[Money, Money]:
    outflow = 0
    inflow = 0
    for ev in events:
        if ev.amount is None or ev.amount.currency != currency:
            continue
        if ev.direction == RecurringDirection.OUTFLOW.value:
            outflow += ev.amount.amount_minor
        elif ev.direction == RecurringDirection.INFLOW.value:
            inflow += ev.amount.amount_minor
    return Money(outflow, currency), Money(inflow, currency)
