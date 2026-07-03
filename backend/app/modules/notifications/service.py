"""Notification use cases: default rules, preferences, and the deterministic scan.

`scan` is the event generator: it walks the planning engines and enqueues idempotent
`NotificationEvent`s (deduped by key). It runs on a schedule (Celery beat) and/or
on-demand. Delivery is via a `Notifier` (in-app now; push/email later).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.domain.enums import (
    ForecastHorizon,
    GoalHealth,
    GoalStatus,
    NotificationChannel,
    NotificationType,
    RecurringKind,
)
from app.domain.ids import new_id
from app.domain.money import Money
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.forecasting import service as forecasting_service
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.notifications import repository as repo
from app.modules.notifications.models import (
    NotificationEvent,
    NotificationPreference,
    NotificationRule,
)
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring.service import occurrences_for_series

_DEFAULT_LEAD = {NotificationType.UPCOMING_BILL: 3, NotificationType.SUBSCRIPTION_RENEWAL: 3}


async def ensure_rules(session: AsyncSession, user_id: uuid.UUID) -> list[NotificationRule]:
    existing = {r.type: r for r in await repo.list_rules(session, user_id)}
    for ntype in NotificationType:
        if ntype not in existing:
            rule = NotificationRule(
                id=new_id(),
                user_id=user_id,
                type=ntype,
                enabled=True,
                lead_time_days=_DEFAULT_LEAD.get(ntype, 0),
                params={},
            )
            repo.add_rule(session, rule)
            existing[ntype] = rule
    await session.flush()
    return list(existing.values())


async def get_or_create_preference(
    session: AsyncSession, user_id: uuid.UUID
) -> NotificationPreference:
    pref = await repo.get_preference(session, user_id)
    if pref is None:
        pref = NotificationPreference(id=new_id(), user_id=user_id)
        repo.add_preference(session, pref)
        await session.flush()
    return pref


async def update_rule(
    session: AsyncSession, *, user_id: uuid.UUID, ntype: NotificationType, changes: dict[str, Any]
) -> NotificationRule:
    await ensure_rules(session, user_id)
    rule = await repo.get_rule(session, user_id, ntype)
    if rule is None:  # pragma: no cover - ensure_rules just created it
        from app.core.errors import NotFoundError

        raise NotFoundError("notification rule not found")
    for key, value in changes.items():
        setattr(rule, key, value)
    await session.flush()
    return rule


async def update_preference(
    session: AsyncSession, *, user_id: uuid.UUID, changes: dict[str, Any]
) -> NotificationPreference:
    pref = await get_or_create_preference(session, user_id)
    for key, value in changes.items():
        setattr(pref, key, value)
    await session.flush()
    return pref


async def mark(
    session: AsyncSession, *, user_id: uuid.UUID, event_id: uuid.UUID, status: object, clock: Clock
) -> None:
    from app.core.errors import NotFoundError
    from app.domain.enums import NotificationStatus

    event = await repo.get_event(session, user_id, event_id)
    if event is None:
        raise NotFoundError("notification not found")
    assert isinstance(status, NotificationStatus)
    event.status = status
    if status is NotificationStatus.READ:
        event.read_at = clock.now()
    await session.flush()


async def _enqueue(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    ntype: NotificationType,
    channel: NotificationChannel,
    title: str,
    body: str,
    dedupe_key: str,
    data: dict[str, Any],
) -> int:
    if await repo.event_exists(session, user_id, dedupe_key):
        return 0
    repo.add_event(
        session,
        NotificationEvent(
            id=new_id(),
            user_id=user_id,
            type=ntype,
            channel=channel,
            title=title,
            body=body,
            data=data,
            dedupe_key=dedupe_key,
        ),
    )
    return 1


async def scan(session: AsyncSession, *, user_id: uuid.UUID, currency: str, clock: Clock) -> int:
    currency = currency.upper()
    now = clock.now()
    rules = {r.type: r for r in await ensure_rules(session, user_id)}
    pref = await get_or_create_preference(session, user_id)
    channel = NotificationChannel.PUSH if pref.push_enabled else NotificationChannel.IN_APP
    month_key = now.strftime("%Y-%m")
    created = 0

    def enabled(t: NotificationType) -> bool:
        return rules[t].enabled

    # Upcoming bills & subscription renewals.
    for series in await recurring_repo.list_active(session, user_id):
        if series.is_subscription:
            ntype = NotificationType.SUBSCRIPTION_RENEWAL
        elif series.kind in (RecurringKind.RENT, RecurringKind.UTILITY, RecurringKind.EMI):
            ntype = NotificationType.UPCOMING_BILL
        else:
            continue
        if not enabled(ntype):
            continue
        end = now + dt.timedelta(days=rules[ntype].lead_time_days)
        amount = Money(series.amount_minor, series.currency)
        for due in occurrences_for_series(series, now, end):
            created += await _enqueue(
                session,
                user_id=user_id,
                ntype=ntype,
                channel=channel,
                title=f"{series.name} due soon",
                body=f"{series.name} ({amount.major} {amount.currency}) is due on {due.date().isoformat()}.",
                dedupe_key=f"{ntype.value}:{series.id}:{due.date().isoformat()}",
                data={"series_id": str(series.id), "due": due.date().isoformat()},
            )

    # Budget warnings.
    if enabled(NotificationType.BUDGET_WARNING):
        for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=100):
            if budget.currency != currency:
                continue
            status = await budgets_service.get_status(
                session, user_id=user_id, budget=budget, as_of=now.date()
            )
            if status.health.value in ("over", "warning"):
                created += await _enqueue(
                    session,
                    user_id=user_id,
                    ntype=NotificationType.BUDGET_WARNING,
                    channel=channel,
                    title=f"{budget.name} {status.health.value}",
                    body=f"{budget.name}: {status.total_spent.major}/{status.total_allocated.major} {currency} spent.",
                    dedupe_key=f"budget_warning:{budget.id}:{status.period_start.isoformat()}:{status.health.value}",
                    data={"budget_id": str(budget.id)},
                )

    # Goal reminders & completions.
    for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=100):
        if goal.currency != currency:
            continue
        projection, _ = await goals_service.get_projection(
            session, user_id=user_id, goal=goal, clock=clock
        )
        if projection.health in (GoalHealth.BEHIND_SCHEDULE, GoalHealth.AT_RISK) and enabled(
            NotificationType.GOAL_REMINDER
        ):
            created += await _enqueue(
                session,
                user_id=user_id,
                ntype=NotificationType.GOAL_REMINDER,
                channel=channel,
                title=f"{goal.name} needs attention",
                body=f"{goal.name} is {projection.health.value.replace('_', ' ')}.",
                dedupe_key=f"goal_reminder:{goal.id}:{month_key}",
                data={"goal_id": str(goal.id)},
            )
        if projection.health is GoalHealth.ACHIEVED and enabled(NotificationType.GOAL_COMPLETION):
            created += await _enqueue(
                session,
                user_id=user_id,
                ntype=NotificationType.GOAL_COMPLETION,
                channel=channel,
                title=f"{goal.name} achieved 🎉",
                body=f"You reached your {goal.name} target.",
                dedupe_key=f"goal_completion:{goal.id}",
                data={"goal_id": str(goal.id)},
            )

    # Forecast warning.
    if enabled(NotificationType.FORECAST_WARNING):
        bundle = await forecasting_service.build_forecast(
            session, user_id=user_id, currency=currency, horizon=ForecastHorizon.D30, clock=clock
        )
        if bundle.cash.projected_negative:
            created += await _enqueue(
                session,
                user_id=user_id,
                ntype=NotificationType.FORECAST_WARNING,
                channel=channel,
                title="Low balance ahead",
                body=f"Balance may dip to {bundle.cash.min_balance.major} {currency} around {bundle.cash.min_balance_date.isoformat()}.",
                dedupe_key=f"forecast_warning:{month_key}",
                data={"min_balance_date": bundle.cash.min_balance_date.isoformat()},
            )

    if created:
        await session.flush()
    return created
