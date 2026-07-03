"""Insight generation — deterministic, explainable financial insights.

Pure functions that turn already-computed facts (growth, projections, budget status,
forecasts) into structured `Insight` objects. No AI, no LLM — every insight is
reproducible arithmetic with an explicit driver. The AI copilot narrates these later; it
never recomputes them (see INSIGHT_ENGINE.md).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.enums import GoalHealth, InsightCategory, InsightSeverity
from app.domain.money import Money


@dataclass(frozen=True, slots=True)
class Insight:
    category: InsightCategory
    severity: InsightSeverity
    title: str
    detail: str
    metric: Money | None = None
    change_pct: Decimal | None = None
    data: dict[str, Any] = field(default_factory=dict)


def _severity_rank(severity: InsightSeverity) -> int:
    return {
        InsightSeverity.CRITICAL: 0,
        InsightSeverity.WARNING: 1,
        InsightSeverity.INFO: 2,
        InsightSeverity.POSITIVE: 3,
    }[severity]


def rank(insights: list[Insight]) -> list[Insight]:
    """Most-actionable first: by severity, then by absolute magnitude of change."""
    return sorted(
        insights,
        key=lambda i: (_severity_rank(i.severity), -abs(i.change_pct or Decimal(0))),
    )


def spending_insight(
    *,
    current: Money,
    previous: Money,
    change_pct: Decimal | None,
    driver_name: str | None,
    driver_delta: Money | None,
    goal_name: str | None = None,
    goal_delay_months: int | None = None,
) -> Insight | None:
    """e.g. 'Food spending increased 23%. Primary driver: Swiggy (+₹1400).'"""
    if change_pct is None or change_pct <= 0:
        return None
    detail_parts = [f"Spending rose {change_pct}% versus the previous period."]
    if driver_name and driver_delta is not None:
        detail_parts.append(
            f"Primary driver: {driver_name} (+{driver_delta.major} {driver_delta.currency})."
        )
    if goal_name and goal_delay_months:
        detail_parts.append(f"Impact: {goal_name} delayed ~{goal_delay_months} month(s).")
    severity = InsightSeverity.WARNING if change_pct >= 15 else InsightSeverity.INFO
    return Insight(
        category=InsightCategory.SPENDING,
        severity=severity,
        title=f"Spending up {change_pct}%",
        detail=" ".join(detail_parts),
        metric=current,
        change_pct=change_pct,
        data={
            "previous_minor": previous.amount_minor,
            "current_minor": current.amount_minor,
            "driver": driver_name,
            "driver_delta_minor": driver_delta.amount_minor if driver_delta else None,
            "goal_delay_months": goal_delay_months,
        },
    )


def goal_insight(
    *, goal_id: uuid.UUID, goal_name: str, health: GoalHealth, required_monthly: Money | None
) -> Insight | None:
    if health in (GoalHealth.BEHIND_SCHEDULE, GoalHealth.AT_RISK):
        needed = (
            f" Contribute {required_monthly.major} {required_monthly.currency}/mo to catch up."
            if required_monthly
            else ""
        )
        return Insight(
            category=InsightCategory.GOAL,
            severity=InsightSeverity.WARNING
            if health is GoalHealth.BEHIND_SCHEDULE
            else InsightSeverity.CRITICAL,
            title=f"{goal_name} is {health.value.replace('_', ' ')}",
            detail=f"{goal_name} is not on track to hit its deadline.{needed}",
            data={"goal_id": str(goal_id), "health": health.value},
        )
    if health is GoalHealth.ACHIEVED:
        return Insight(
            category=InsightCategory.GOAL,
            severity=InsightSeverity.POSITIVE,
            title=f"{goal_name} achieved",
            detail=f"You reached your {goal_name} target. 🎉",
            data={"goal_id": str(goal_id), "health": health.value},
        )
    return None


def budget_insight(
    *, budget_id: uuid.UUID, budget_name: str, is_over: bool, is_warning: bool, remaining: Money
) -> Insight | None:
    if is_over:
        return Insight(
            category=InsightCategory.BUDGET,
            severity=InsightSeverity.CRITICAL,
            title=f"{budget_name} overspent",
            detail=f"You are over budget by {(-remaining).major} {remaining.currency}.",
            metric=remaining,
            data={"budget_id": str(budget_id)},
        )
    if is_warning:
        return Insight(
            category=InsightCategory.BUDGET,
            severity=InsightSeverity.WARNING,
            title=f"{budget_name} nearly spent",
            detail=f"Only {remaining.major} {remaining.currency} of this budget remains.",
            metric=remaining,
            data={"budget_id": str(budget_id)},
        )
    return None


def subscription_insight(*, inactive_count: int, monthly_cost: Money) -> Insight | None:
    if inactive_count <= 0:
        return None
    return Insight(
        category=InsightCategory.SUBSCRIPTION,
        severity=InsightSeverity.INFO,
        title=f"{inactive_count} unused subscription(s)",
        detail=f"You have {inactive_count} subscription(s) with no recent activity, costing {monthly_cost.major} {monthly_cost.currency}/mo. Consider cancelling.",
        metric=monthly_cost,
        data={"inactive_count": inactive_count},
    )


def forecast_insight(
    *, projected_negative: bool, min_balance: Money, min_balance_date_iso: str
) -> Insight | None:
    if not projected_negative:
        return None
    return Insight(
        category=InsightCategory.FORECAST,
        severity=InsightSeverity.CRITICAL,
        title="Projected low balance",
        detail=f"Your balance is projected to dip to {min_balance.major} {min_balance.currency} around {min_balance_date_iso}.",
        metric=min_balance,
        data={"min_balance_date": min_balance_date_iso},
    )
