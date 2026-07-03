"""Unit tests for the pure insight generators."""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.domain.enums import GoalHealth, InsightCategory, InsightSeverity
from app.domain.insights import (
    budget_insight,
    forecast_insight,
    goal_insight,
    rank,
    spending_insight,
    subscription_insight,
)
from app.domain.money import Money


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_spending_insight_with_driver_and_goal_impact() -> None:
    ins = spending_insight(
        current=_m(6150),
        previous=_m(5000),
        change_pct=Decimal("23.0"),
        driver_name="Swiggy",
        driver_delta=_m(1400),
        goal_name="Masters",
        goal_delay_months=1,
    )
    assert ins is not None
    assert ins.category is InsightCategory.SPENDING
    assert ins.severity is InsightSeverity.WARNING  # >= 15%
    assert "Swiggy" in ins.detail
    assert "Masters" in ins.detail
    assert ins.change_pct == Decimal("23.0")


def test_spending_insight_none_when_flat_or_down() -> None:
    assert (
        spending_insight(
            current=_m(100),
            previous=_m(200),
            change_pct=Decimal("-50.0"),
            driver_name=None,
            driver_delta=None,
        )
        is None
    )
    assert (
        spending_insight(
            current=_m(100), previous=_m(100), change_pct=None, driver_name=None, driver_delta=None
        )
        is None
    )


def test_spending_small_rise_is_info() -> None:
    ins = spending_insight(
        current=_m(103),
        previous=_m(100),
        change_pct=Decimal("3.0"),
        driver_name=None,
        driver_delta=None,
    )
    assert ins is not None and ins.severity is InsightSeverity.INFO


def test_goal_insight_behind_and_achieved() -> None:
    gid = uuid.uuid4()
    behind = goal_insight(
        goal_id=gid, goal_name="Trip", health=GoalHealth.BEHIND_SCHEDULE, required_monthly=_m(5000)
    )
    assert behind is not None and behind.severity is InsightSeverity.WARNING
    at_risk = goal_insight(
        goal_id=gid, goal_name="Trip", health=GoalHealth.AT_RISK, required_monthly=None
    )
    assert at_risk is not None and at_risk.severity is InsightSeverity.CRITICAL
    done = goal_insight(
        goal_id=gid, goal_name="Trip", health=GoalHealth.ACHIEVED, required_monthly=None
    )
    assert done is not None and done.severity is InsightSeverity.POSITIVE
    ok = goal_insight(
        goal_id=gid, goal_name="Trip", health=GoalHealth.ON_TRACK, required_monthly=None
    )
    assert ok is None


def test_budget_insight() -> None:
    bid = uuid.uuid4()
    over = budget_insight(
        budget_id=bid,
        budget_name="Food",
        is_over=True,
        is_warning=False,
        remaining=Money(-50000, "INR"),
    )
    assert over is not None and over.severity is InsightSeverity.CRITICAL
    warn = budget_insight(
        budget_id=bid, budget_name="Food", is_over=False, is_warning=True, remaining=_m(200)
    )
    assert warn is not None and warn.severity is InsightSeverity.WARNING
    assert (
        budget_insight(
            budget_id=bid, budget_name="Food", is_over=False, is_warning=False, remaining=_m(2000)
        )
        is None
    )


def test_subscription_and_forecast_insights() -> None:
    assert subscription_insight(inactive_count=0, monthly_cost=_m(0)) is None
    sub = subscription_insight(inactive_count=2, monthly_cost=_m(500))
    assert sub is not None and "2" in sub.title
    assert (
        forecast_insight(
            projected_negative=False, min_balance=_m(1000), min_balance_date_iso="2026-07-30"
        )
        is None
    )
    fc = forecast_insight(
        projected_negative=True, min_balance=Money(-1000, "INR"), min_balance_date_iso="2026-07-30"
    )
    assert fc is not None and fc.severity is InsightSeverity.CRITICAL


def test_rank_orders_by_severity() -> None:
    gid = uuid.uuid4()
    items = [
        goal_insight(goal_id=gid, goal_name="A", health=GoalHealth.ACHIEVED, required_monthly=None),
        goal_insight(goal_id=gid, goal_name="B", health=GoalHealth.AT_RISK, required_monthly=None),
    ]
    ordered = rank([i for i in items if i is not None])
    assert ordered[0].severity is InsightSeverity.CRITICAL
    assert ordered[-1].severity is InsightSeverity.POSITIVE
