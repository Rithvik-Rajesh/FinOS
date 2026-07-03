"""Tests for the budget calculation engine."""

from __future__ import annotations

import datetime as dt
import uuid

from app.domain.budgets import assess_budget, assess_line
from app.domain.enums import BudgetHealth
from app.domain.money import Money

CAT = uuid.uuid4()
START = dt.date(2026, 7, 1)
END = dt.date(2026, 7, 30)


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_under_budget() -> None:
    line = assess_line(
        category_id=CAT,
        allocated=_m(5000),
        spent=_m(3000),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 15),
    )
    assert line.health is BudgetHealth.UNDER
    assert line.remaining == _m(2000)
    assert line.utilization_ratio == 0.6


def test_warning_threshold() -> None:
    line = assess_line(
        category_id=CAT,
        allocated=_m(5000),
        spent=_m(4200),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 28),
    )
    assert line.health is BudgetHealth.WARNING  # 84% >= 80%
    assert line.remaining == _m(800)


def test_overspent() -> None:
    line = assess_line(
        category_id=CAT,
        allocated=_m(5000),
        spent=_m(6000),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 20),
    )
    assert line.health is BudgetHealth.OVER
    assert line.remaining == Money(-100000, "INR")


def test_zero_allocation_with_spend_is_over() -> None:
    line = assess_line(
        category_id=None,
        allocated=_m(0),
        spent=_m(500),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 5),
    )
    assert line.health is BudgetHealth.OVER
    assert line.utilization_ratio is None
    assert line.projected_exhaustion is None


def test_projected_exhaustion_date() -> None:
    # 1,500 spent in the first 10 days on a 3,000 allocation -> exhaust by the 20th.
    line = assess_line(
        category_id=CAT,
        allocated=_m(3000),
        spent=_m(1500),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 10),
    )
    assert line.projected_spend == _m(4500)  # run-rate over 30 days
    assert line.projected_exhaustion == dt.date(2026, 7, 20)


def test_no_spend_has_no_projection() -> None:
    line = assess_line(
        category_id=CAT,
        allocated=_m(3000),
        spent=_m(0),
        period_start=START,
        period_end=END,
        as_of=dt.date(2026, 7, 10),
    )
    assert line.projected_spend is None
    assert line.health is BudgetHealth.UNDER


def test_budget_rollup() -> None:
    lines = [
        assess_line(
            category_id=CAT,
            allocated=_m(5000),
            spent=_m(3000),
            period_start=START,
            period_end=END,
            as_of=dt.date(2026, 7, 15),
        ),
        assess_line(
            category_id=uuid.uuid4(),
            allocated=_m(2000),
            spent=_m(2500),
            period_start=START,
            period_end=END,
            as_of=dt.date(2026, 7, 15),
        ),
    ]
    status = assess_budget(lines=lines, currency="INR", period_start=START, period_end=END)
    assert status.total_allocated == _m(7000)
    assert status.total_spent == _m(5500)
    assert status.total_remaining == _m(1500)
    assert status.health is BudgetHealth.UNDER  # 5500/7000 = 78.6% < 80%
