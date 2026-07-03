"""Subscription cost math — deterministic normalization to monthly/annual.

A subscription is a specialization of a recurring series (ADR-007). This module turns a
per-cycle price into normalized monthly and annual costs so mixed billing cycles can be
summed and compared. Annual is exact; monthly is the annual divided by 12.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.enums import BillingCycle
from app.domain.money import Money

_CYCLES_PER_YEAR = {
    BillingCycle.WEEKLY: 52,
    BillingCycle.MONTHLY: 12,
    BillingCycle.QUARTERLY: 4,
    BillingCycle.YEARLY: 1,
}


@dataclass(frozen=True, slots=True)
class SubscriptionCost:
    monthly: Money
    annual: Money


def normalize_cost(amount: Money, cycle: BillingCycle) -> SubscriptionCost:
    annual_minor = amount.amount_minor * _CYCLES_PER_YEAR[cycle]
    return SubscriptionCost(
        monthly=Money(annual_minor // 12, amount.currency),
        annual=Money(annual_minor, amount.currency),
    )


def aggregate_cost(items: Iterable[tuple[Money, BillingCycle]], currency: str) -> SubscriptionCost:
    """Sum normalized costs across a set of subscriptions (same currency)."""
    monthly = 0
    annual = 0
    for amount, cycle in items:
        cost = normalize_cost(amount, cycle)
        monthly += cost.monthly.amount_minor
        annual += cost.annual.amount_minor
    return SubscriptionCost(Money(monthly, currency), Money(annual, currency))
