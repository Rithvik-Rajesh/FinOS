"""Financial decision engine — deterministic purchase / EMI / goal-impact math.

Pure calculations that a future AI assistant will *call* but never replace. Every output
is reproducible arithmetic; there is no advice, no heuristic, no model.
See SIMULATION_ENGINE.md.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.goals import GoalProjection, months_between, project_goal
from app.domain.money import Money


# --------------------------------------------------------------------------- #
# EMI (loan amortization)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class EmiPlan:
    principal: Money
    annual_rate_bps: int  # basis points, e.g. 1050 == 10.50%
    months: int
    monthly_payment: Money
    total_payment: Money
    total_interest: Money


def compute_emi(*, principal: Money, annual_rate_bps: int, months: int) -> EmiPlan:
    """Standard reducing-balance EMI. Deterministic via Decimal, rounded to minor units."""
    if months <= 0:
        raise ValueError("months must be positive")
    if annual_rate_bps < 0:
        raise ValueError("annual_rate_bps must be >= 0")

    p = Decimal(principal.amount_minor)
    if annual_rate_bps == 0:
        emi_minor = int((p / months).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    else:
        r = Decimal(annual_rate_bps) / Decimal(10000) / Decimal(12)
        factor = (Decimal(1) + r) ** months
        emi = p * r * factor / (factor - Decimal(1))
        emi_minor = int(emi.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    total = emi_minor * months
    return EmiPlan(
        principal=principal,
        annual_rate_bps=annual_rate_bps,
        months=months,
        monthly_payment=Money(emi_minor, principal.currency),
        total_payment=Money(total, principal.currency),
        total_interest=Money(total - principal.amount_minor, principal.currency),
    )


# --------------------------------------------------------------------------- #
# Goal impact
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class GoalImpact:
    goal_id: uuid.UUID
    name: str
    baseline_completion: dt.date | None
    impacted_completion: dt.date | None
    delay_months: int | None  # None when either projection is open-ended


@dataclass(frozen=True, slots=True)
class GoalSimInput:
    goal_id: uuid.UUID
    name: str
    target: Money
    current: Money
    deadline: dt.date | None
    observed_monthly: Money


def analyze_goal_impact(
    goal: GoalSimInput, *, reduce_current_by: Money, as_of: dt.date
) -> GoalImpact:
    """How does spending `reduce_current_by` out of this goal's savings delay it?"""
    baseline = project_goal(
        target=goal.target,
        current=goal.current,
        deadline=goal.deadline,
        observed_monthly=goal.observed_monthly,
        as_of=as_of,
    )
    impacted_current = Money(
        max(0, goal.current.amount_minor - reduce_current_by.amount_minor), goal.current.currency
    )
    impacted = project_goal(
        target=goal.target,
        current=impacted_current,
        deadline=goal.deadline,
        observed_monthly=goal.observed_monthly,
        as_of=as_of,
    )
    return GoalImpact(
        goal_id=goal.goal_id,
        name=goal.name,
        baseline_completion=baseline.projected_completion,
        impacted_completion=impacted.projected_completion,
        delay_months=_delay_months(baseline, impacted),
    )


def _delay_months(baseline: GoalProjection, impacted: GoalProjection) -> int | None:
    if baseline.projected_completion is None or impacted.projected_completion is None:
        return None
    return months_between(baseline.projected_completion, impacted.projected_completion)


# --------------------------------------------------------------------------- #
# Purchase simulation
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PurchaseSimulation:
    amount: Money
    cash_before: Money
    cash_after: Money
    affordable_from_cash: bool  # cash stays at/above the emergency floor
    emergency_floor: Money
    monthly_surplus_before: Money
    monthly_surplus_after: Money  # if paid via EMI, surplus drops by the EMI
    goal_impacts: tuple[GoalImpact, ...]
    emi: EmiPlan | None


def simulate_purchase(
    *,
    amount: Money,
    cash_before: Money,
    emergency_floor: Money,
    monthly_surplus: Money,
    goals: list[GoalSimInput],
    as_of: dt.date,
    emi: EmiPlan | None = None,
) -> PurchaseSimulation:
    """Deterministic impact of a purchase.

    If `emi` is provided the purchase is financed: cash is unchanged but monthly surplus
    drops by the EMI and goals are unaffected by a cash drawdown. Otherwise it is paid
    from cash, and goals funded from that cash are delayed.
    """
    if emi is not None:
        cash_after = cash_before
        surplus_after = monthly_surplus - emi.monthly_payment
        impacts: tuple[GoalImpact, ...] = ()
    else:
        cash_after = cash_before - amount
        surplus_after = monthly_surplus
        impacts = tuple(
            analyze_goal_impact(goal, reduce_current_by=amount, as_of=as_of) for goal in goals
        )

    affordable = cash_after.amount_minor >= emergency_floor.amount_minor
    return PurchaseSimulation(
        amount=amount,
        cash_before=cash_before,
        cash_after=cash_after,
        affordable_from_cash=affordable,
        emergency_floor=emergency_floor,
        monthly_surplus_before=monthly_surplus,
        monthly_surplus_after=surplus_after,
        goal_impacts=impacts,
        emi=emi,
    )
