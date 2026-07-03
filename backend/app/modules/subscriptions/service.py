"""Subscription analytics — built on recurring series (ADR-007).

Cost math is delegated to the pure `app.domain.subscriptions` engine; inactivity is
determined from the ledger. All deterministic.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.domain.enums import BillingCycle, RecurrenceInterval, RecurringStatus
from app.domain.money import Money
from app.domain.subscriptions import SubscriptionCost, aggregate_cost
from app.modules.ledger.lookups import merchant_last_seen
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring.models import RecurringSeries

_INTERVAL_TO_CYCLE = {
    RecurrenceInterval.DAILY: BillingCycle.MONTHLY,  # normalized via 30-day month fallback
    RecurrenceInterval.WEEKLY: BillingCycle.WEEKLY,
    RecurrenceInterval.MONTHLY: BillingCycle.MONTHLY,
    RecurrenceInterval.QUARTERLY: BillingCycle.QUARTERLY,
    RecurrenceInterval.YEARLY: BillingCycle.YEARLY,
}


def _cycle(series: RecurringSeries) -> BillingCycle:
    return series.billing_cycle or _INTERVAL_TO_CYCLE[series.interval]


async def list_active(session: AsyncSession, user_id: uuid.UUID) -> list[RecurringSeries]:
    rows = await recurring_repo.list_(
        session, user_id, status=RecurringStatus.ACTIVE, is_subscription=True, limit=1000
    )
    return list(rows)


async def summary(
    session: AsyncSession, *, user_id: uuid.UUID, currency: str
) -> tuple[SubscriptionCost, int]:
    subs = [s for s in await list_active(session, user_id) if s.currency == currency.upper()]
    cost = aggregate_cost(
        ((Money(s.amount_minor, s.currency), _cycle(s)) for s in subs), currency=currency.upper()
    )
    return cost, len(subs)


@dataclass(frozen=True, slots=True)
class Inactive:
    series: RecurringSeries
    last_seen: dt.datetime | None
    days_inactive: int | None


async def inactive(
    session: AsyncSession, *, user_id: uuid.UUID, clock: Clock, inactive_days: int
) -> list[Inactive]:
    """Active subscriptions with no matching merchant transaction within the window."""
    now = clock.now()
    threshold = now - dt.timedelta(days=inactive_days)
    result: list[Inactive] = []
    for series in await list_active(session, user_id):
        if series.merchant_id is None:
            continue
        last = await merchant_last_seen(session, user_id, series.merchant_id)
        if last is None:
            result.append(Inactive(series, None, None))
        elif last < threshold:
            result.append(Inactive(series, last, (now - last).days))
    return result


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


async def upcoming_renewals(
    session: AsyncSession, *, user_id: uuid.UUID, within_days: int, clock: Clock
) -> list[RecurringSeries]:
    horizon = clock.now() + dt.timedelta(days=within_days)
    return [s for s in await list_active(session, user_id) if _aware(s.next_due_at) <= horizon]
