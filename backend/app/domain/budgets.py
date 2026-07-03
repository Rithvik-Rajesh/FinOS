"""Budget calculations — utilization, remaining, overspend, projected exhaustion.

Pure and deterministic. `spent` is supplied by the caller (computed from the ledger via
the reporting engine); this module never touches I/O. See BUDGET_ENGINE.md.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from app.domain.enums import BudgetHealth
from app.domain.money import Money

DEFAULT_WARNING_RATIO = 0.8  # 80% of allocation triggers a warning


@dataclass(frozen=True, slots=True)
class BudgetLineStatus:
    category_id: uuid.UUID | None  # None == the global/overall budget line
    allocated: Money
    spent: Money
    remaining: Money  # allocated - spent (negative when overspent)
    utilization_ratio: float | None  # spent/allocated; None when allocation is zero
    health: BudgetHealth
    projected_spend: Money | None  # end-of-period run-rate projection
    projected_exhaustion: dt.date | None  # when spend is projected to hit the allocation


def _days_inclusive(start: dt.date, end: dt.date) -> int:
    return (end - start).days + 1


def assess_line(
    *,
    category_id: uuid.UUID | None,
    allocated: Money,
    spent: Money,
    period_start: dt.date,
    period_end: dt.date,
    as_of: dt.date,
    warning_ratio: float = DEFAULT_WARNING_RATIO,
) -> BudgetLineStatus:
    remaining = allocated - spent  # raises on currency mismatch
    alloc_minor = allocated.amount_minor
    spent_minor = spent.amount_minor

    if alloc_minor <= 0:
        utilization = None
        health = BudgetHealth.OVER if spent_minor > 0 else BudgetHealth.UNDER
    else:
        utilization = spent_minor / alloc_minor
        if spent_minor > alloc_minor:
            health = BudgetHealth.OVER
        elif utilization >= warning_ratio:
            health = BudgetHealth.WARNING
        else:
            health = BudgetHealth.UNDER

    projected_spend: Money | None = None
    projected_exhaustion: dt.date | None = None
    if alloc_minor > 0 and spent_minor > 0:
        elapsed = _days_inclusive(period_start, min(as_of, period_end))
        elapsed = max(1, elapsed)
        total = _days_inclusive(period_start, period_end)
        projected_minor = spent_minor * total // elapsed
        projected_spend = Money(projected_minor, allocated.currency)
        # Exhaustion: days from period start until run-rate spend reaches the allocation.
        if projected_minor > alloc_minor:
            days_to_exhaust = -(-(alloc_minor * elapsed) // spent_minor)  # ceil
            projected_exhaustion = period_start + dt.timedelta(days=days_to_exhaust - 1)

    return BudgetLineStatus(
        category_id=category_id,
        allocated=allocated,
        spent=spent,
        remaining=remaining,
        utilization_ratio=utilization,
        health=health,
        projected_spend=projected_spend,
        projected_exhaustion=projected_exhaustion,
    )


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    period_start: dt.date
    period_end: dt.date
    total_allocated: Money
    total_spent: Money
    total_remaining: Money
    utilization_ratio: float | None
    health: BudgetHealth
    lines: tuple[BudgetLineStatus, ...]


def assess_budget(
    *,
    lines: list[BudgetLineStatus],
    currency: str,
    period_start: dt.date,
    period_end: dt.date,
    warning_ratio: float = DEFAULT_WARNING_RATIO,
) -> BudgetStatus:
    allocated = Money(sum(line.allocated.amount_minor for line in lines), currency)
    spent = Money(sum(line.spent.amount_minor for line in lines), currency)
    remaining = allocated - spent
    if allocated.amount_minor <= 0:
        utilization = None
        health = BudgetHealth.OVER if spent.amount_minor > 0 else BudgetHealth.UNDER
    else:
        utilization = spent.amount_minor / allocated.amount_minor
        if spent.amount_minor > allocated.amount_minor:
            health = BudgetHealth.OVER
        elif utilization >= warning_ratio:
            health = BudgetHealth.WARNING
        else:
            health = BudgetHealth.UNDER
    return BudgetStatus(
        period_start=period_start,
        period_end=period_end,
        total_allocated=allocated,
        total_spent=spent,
        total_remaining=remaining,
        utilization_ratio=utilization,
        health=health,
        lines=tuple(lines),
    )
