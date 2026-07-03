"""Tests for the financial decision (simulation) engine."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest

from app.domain.money import Money
from app.domain.simulation import (
    GoalSimInput,
    analyze_goal_impact,
    compute_emi,
    simulate_purchase,
)

AS_OF = dt.date(2026, 7, 1)


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_emi_standard() -> None:
    plan = compute_emi(principal=_m(100000), annual_rate_bps=1200, months=12)  # ₹1L @ 12%/12m
    # Known EMI ≈ ₹8,884.88.
    assert abs(plan.monthly_payment.amount_minor - 888488) <= 2
    assert plan.total_payment.amount_minor == plan.monthly_payment.amount_minor * 12
    assert plan.total_interest.amount_minor > 0


def test_emi_zero_interest() -> None:
    plan = compute_emi(principal=_m(120000), annual_rate_bps=0, months=12)
    assert plan.monthly_payment == _m(10000)
    assert plan.total_interest == _m(0)


def test_emi_invalid_months() -> None:
    with pytest.raises(ValueError):
        compute_emi(principal=_m(1000), annual_rate_bps=1000, months=0)


def test_purchase_from_cash_affordable() -> None:
    sim = simulate_purchase(
        amount=_m(95000),
        cash_before=_m(200000),
        emergency_floor=_m(50000),
        monthly_surplus=_m(20000),
        goals=[],
        as_of=AS_OF,
    )
    assert sim.cash_after == _m(105000)
    assert sim.affordable_from_cash is True


def test_purchase_breaches_emergency_floor() -> None:
    sim = simulate_purchase(
        amount=_m(95000),
        cash_before=_m(120000),
        emergency_floor=_m(50000),
        monthly_surplus=_m(20000),
        goals=[],
        as_of=AS_OF,
    )
    assert sim.cash_after == _m(25000)
    assert sim.affordable_from_cash is False  # 25k < 50k floor


def test_goal_impact_delay() -> None:
    goal = GoalSimInput(
        goal_id=uuid.uuid4(),
        name="Laptop",
        target=_m(100000),
        current=_m(50000),
        deadline=None,
        observed_monthly=_m(5000),
    )
    impact = analyze_goal_impact(goal, reduce_current_by=_m(30000), as_of=AS_OF)
    # baseline: 50k left / 5k = 10 months; impacted: 80k left / 5k = 16 months.
    assert impact.delay_months == 6


def test_emi_financed_purchase_reduces_surplus_not_cash() -> None:
    emi = compute_emi(principal=_m(95000), annual_rate_bps=1500, months=12)
    goal = GoalSimInput(
        goal_id=uuid.uuid4(),
        name="Trip",
        target=_m(100000),
        current=_m(50000),
        deadline=None,
        observed_monthly=_m(5000),
    )
    sim = simulate_purchase(
        amount=_m(95000),
        cash_before=_m(120000),
        emergency_floor=_m(50000),
        monthly_surplus=_m(20000),
        goals=[goal],
        as_of=AS_OF,
        emi=emi,
    )
    assert sim.cash_after == _m(120000)  # cash untouched
    assert sim.monthly_surplus_after == _m(20000) - emi.monthly_payment
    assert sim.goal_impacts == ()  # goals unaffected by financing
