"""Tests for subscription cost normalization."""

from __future__ import annotations

from app.domain.enums import BillingCycle
from app.domain.money import Money
from app.domain.subscriptions import aggregate_cost, normalize_cost


def _inr(minor: int) -> Money:
    return Money(minor, "INR")


def test_monthly_normalization() -> None:
    cost = normalize_cost(_inr(64900), BillingCycle.MONTHLY)  # ₹649
    assert cost.annual == _inr(64900 * 12)
    assert cost.monthly == _inr(64900)


def test_weekly_normalization() -> None:
    cost = normalize_cost(_inr(11900), BillingCycle.WEEKLY)  # ₹119/week
    assert cost.annual == _inr(11900 * 52)
    assert cost.monthly == _inr(11900 * 52 // 12)


def test_quarterly_and_yearly() -> None:
    q = normalize_cost(_inr(30000), BillingCycle.QUARTERLY)
    assert q.annual == _inr(120000)
    assert q.monthly == _inr(10000)
    y = normalize_cost(_inr(120000), BillingCycle.YEARLY)
    assert y.annual == _inr(120000)
    assert y.monthly == _inr(10000)


def test_aggregate_mixed_cycles() -> None:
    total = aggregate_cost(
        [
            (_inr(64900), BillingCycle.MONTHLY),
            (_inr(120000), BillingCycle.YEARLY),
            (_inr(30000), BillingCycle.QUARTERLY),
        ],
        currency="INR",
    )
    # annual: 778800 + 120000 + 120000 = 1,018,800
    assert total.annual == _inr(1018800)
    assert total.monthly == _inr(1018800 // 12)
