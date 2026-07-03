"""Tests for the goal projection engine."""

from __future__ import annotations

import datetime as dt

from app.domain.enums import GoalHealth
from app.domain.goals import project_goal
from app.domain.money import Money

AS_OF = dt.date(2026, 7, 1)


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_achieved_goal() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(100000),
        deadline=dt.date(2027, 1, 1),
        observed_monthly=_m(5000),
        as_of=AS_OF,
    )
    assert p.health is GoalHealth.ACHIEVED
    assert p.remaining == _m(0)
    assert p.progress_ratio == 1.0
    assert p.projected_completion == AS_OF


def test_no_deadline() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(20000),
        deadline=None,
        observed_monthly=_m(5000),
        as_of=AS_OF,
    )
    assert p.health is GoalHealth.NO_DEADLINE
    assert p.required_monthly is None
    # 80,000 remaining / 5,000 per month = 16 months.
    assert p.projected_completion == dt.date(2027, 11, 1)


def test_required_monthly_to_hit_deadline() -> None:
    # 90,000 remaining over 9 months -> 10,000/month.
    p = project_goal(
        target=_m(100000),
        current=_m(10000),
        deadline=dt.date(2027, 4, 1),
        observed_monthly=_m(10000),
        as_of=AS_OF,
    )
    assert p.required_monthly == _m(10000)
    assert p.health is GoalHealth.ON_TRACK


def test_behind_when_rate_too_low() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(10000),
        deadline=dt.date(2027, 4, 1),
        observed_monthly=_m(1000),
        as_of=AS_OF,
    )
    assert p.health is GoalHealth.BEHIND_SCHEDULE
    assert p.projected_completion is not None
    assert p.projected_completion > dt.date(2027, 4, 1)


def test_behind_when_no_contributions() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(10000),
        deadline=dt.date(2027, 4, 1),
        observed_monthly=_m(0),
        as_of=AS_OF,
    )
    assert p.projected_completion is None  # never at this rate
    assert p.health is GoalHealth.BEHIND_SCHEDULE


def test_ahead_with_buffer() -> None:
    # 20,000 remaining, 10,000/month -> done in 2 months (Sep 2026), well before deadline.
    p = project_goal(
        target=_m(100000),
        current=_m(80000),
        deadline=dt.date(2027, 6, 1),
        observed_monthly=_m(10000),
        as_of=AS_OF,
    )
    assert p.health is GoalHealth.AHEAD


def test_at_risk_past_deadline() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(50000),
        deadline=dt.date(2026, 1, 1),
        observed_monthly=_m(5000),
        as_of=AS_OF,
    )
    assert p.health is GoalHealth.AT_RISK
    assert p.required_monthly == _m(50000)  # whole remainder is due now


def test_progress_ratio_clamped() -> None:
    p = project_goal(
        target=_m(100000),
        current=_m(30000),
        deadline=None,
        observed_monthly=_m(0),
        as_of=AS_OF,
    )
    assert p.progress_ratio == 0.3
