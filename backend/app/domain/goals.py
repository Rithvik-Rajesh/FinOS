"""Goal projection — deterministic progress, required contribution, and completion.

Pure math over a goal's target, current amount, deadline, and observed monthly
contribution rate. No AI, no statistics — transparent arithmetic (see GOALS_ENGINE.md).
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from app.domain.enums import GoalHealth
from app.domain.money import Money

# Beyond this many months at the current rate we treat completion as "not foreseeable".
_MAX_PROJECTION_MONTHS = 1200  # 100 years


def add_months(base: dt.date, months: int) -> dt.date:
    index = base.month - 1 + months
    year = base.year + index // 12
    month = index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def months_between(start: dt.date, end: dt.date) -> int:
    """Whole calendar months from `start` to `end` (>= 0 when end >= start)."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    return -(-numerator // denominator)


@dataclass(frozen=True, slots=True)
class GoalProjection:
    target: Money
    current: Money
    remaining: Money
    progress_ratio: float  # 0.0–1.0, clamped
    required_monthly: Money | None  # to hit the deadline; None if no future deadline
    observed_monthly: Money  # the rate used for the completion estimate
    projected_completion: dt.date | None  # None if unreachable at the observed rate
    months_to_deadline: int | None
    health: GoalHealth


def project_goal(
    *,
    target: Money,
    current: Money,
    deadline: dt.date | None,
    observed_monthly: Money,
    as_of: dt.date,
) -> GoalProjection:
    """Project a goal deterministically. All money is same-currency (validated by Money)."""
    remaining_minor = max(0, target.amount_minor - current.amount_minor)
    remaining = Money(remaining_minor, target.currency)
    progress = (
        1.0
        if target.amount_minor <= 0
        else min(1.0, max(0.0, current.amount_minor / target.amount_minor))
    )

    achieved = current.amount_minor >= target.amount_minor

    # Required monthly contribution to hit the deadline.
    months_to_deadline: int | None = None
    required_monthly: Money | None = None
    if deadline is not None:
        months_to_deadline = months_between(as_of, deadline)
        if not achieved and months_to_deadline is not None and months_to_deadline >= 1:
            required_monthly = Money(
                _ceil_div(remaining_minor, months_to_deadline), target.currency
            )
        elif not achieved:
            # Deadline is this month or already passed; the whole remainder is "due now".
            required_monthly = remaining

    # Projected completion at the observed contribution rate.
    projected_completion: dt.date | None = None
    if achieved:
        projected_completion = as_of
    elif observed_monthly.amount_minor > 0:
        months_needed = _ceil_div(remaining_minor, observed_monthly.amount_minor)
        if months_needed <= _MAX_PROJECTION_MONTHS:
            projected_completion = add_months(as_of, months_needed)

    health = _health(
        achieved=achieved,
        deadline=deadline,
        as_of=as_of,
        projected_completion=projected_completion,
    )
    return GoalProjection(
        target=target,
        current=current,
        remaining=remaining,
        progress_ratio=progress,
        required_monthly=required_monthly,
        observed_monthly=observed_monthly,
        projected_completion=projected_completion,
        months_to_deadline=months_to_deadline,
        health=health,
    )


def _health(
    *,
    achieved: bool,
    deadline: dt.date | None,
    as_of: dt.date,
    projected_completion: dt.date | None,
) -> GoalHealth:
    if achieved:
        return GoalHealth.ACHIEVED
    if deadline is None:
        return GoalHealth.NO_DEADLINE
    if deadline < as_of:
        return GoalHealth.AT_RISK
    if projected_completion is None or projected_completion > deadline:
        return GoalHealth.BEHIND_SCHEDULE
    # On track; call it "ahead" only with a clear month of buffer.
    if projected_completion <= add_months(deadline, -1):
        return GoalHealth.AHEAD
    return GoalHealth.ON_TRACK
