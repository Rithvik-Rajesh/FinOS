"""Budget use cases: CRUD, on-read status, and event-driven alerts.

Spend is computed from the ledger (via the reporting engine) for the current period and
assessed with the pure `app.domain.budgets` engine. Nothing about utilization is stored,
so a budget always reflects real spending (ADR-011).
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.budgets import BudgetLineStatus, BudgetStatus, assess_budget, assess_line
from app.domain.clock import Clock
from app.domain.enums import BudgetHealth, BudgetPeriodType
from app.domain.goals import add_months
from app.domain.ids import new_id
from app.domain.money import Money
from app.domain.reporting import spending_by_category, total_spending
from app.modules.audit.repository import record as audit_record
from app.modules.budgets import repository as repo
from app.modules.budgets.models import Budget, BudgetAlert, BudgetCategoryAllocation
from app.modules.budgets.schemas import AllocationInput, BudgetCreate, BudgetUpdate
from app.modules.ledger.records import reporting_records

_DEFAULT_CUSTOM_DAYS = 30


def period_bounds(budget: Budget, as_of: dt.date, offset: int) -> tuple[dt.date, dt.date]:
    """Deterministic [start, end] dates for the period `offset` from the one containing as_of."""
    if budget.period_type is BudgetPeriodType.MONTHLY:
        base = add_months(dt.date(as_of.year, as_of.month, 1), offset)
        return base, add_months(base, 1) - dt.timedelta(days=1)
    if budget.period_type is BudgetPeriodType.WEEKLY:
        monday = as_of - dt.timedelta(days=as_of.weekday())
        start = monday + dt.timedelta(days=7 * offset)
        return start, start + dt.timedelta(days=6)
    days = budget.custom_period_days or _DEFAULT_CUSTOM_DAYS
    anchor = budget.created_at.date()
    index = (as_of - anchor).days // days
    start = anchor + dt.timedelta(days=(index + offset) * days)
    return start, start + dt.timedelta(days=days - 1)


async def _create_allocations(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    budget_id: uuid.UUID,
    currency: str,
    allocations: list[AllocationInput],
) -> None:
    for alloc in allocations:
        session_obj = BudgetCategoryAllocation(
            id=new_id(),
            user_id=user_id,
            budget_id=budget_id,
            category_id=alloc.category_id,
            amount_minor=alloc.amount_minor,
            currency=currency,
            version=1,
            server_seq=await next_server_seq(session, user_id),
        )
        repo.add_allocation(session, session_obj)


async def create_budget(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: BudgetCreate,
    correlation_id: str | None = None,
) -> Budget:
    budget_id = data.id or new_id()
    existing = await repo.get(session, user_id, budget_id)
    if existing is not None:
        return existing
    budget = Budget(
        id=budget_id,
        user_id=user_id,
        name=data.name,
        period_type=data.period_type,
        currency=data.currency.upper(),
        overall_amount_minor=data.overall_amount_minor,
        custom_period_days=data.custom_period_days,
        is_active=True,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, budget)
    await _create_allocations(
        session,
        user_id=user_id,
        budget_id=budget_id,
        currency=budget.currency,
        allocations=data.allocations,
    )
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="budget",
        entity_id=budget_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name},
    )
    await session.flush()
    return budget


async def update_budget(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    budget_id: uuid.UUID,
    data: BudgetUpdate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Budget:
    budget = await repo.get(session, user_id, budget_id)
    if budget is None:
        raise NotFoundError("budget not found")
    fields = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    for key in ("name", "overall_amount_minor", "is_active"):
        if key in fields and getattr(budget, key) != fields[key]:
            setattr(budget, key, fields[key])
            changed[key] = fields[key]

    if data.allocations is not None:
        for existing in await repo.allocations(session, user_id, budget_id):
            existing.deleted_at = clock.now()
            existing.version += 1
            existing.server_seq = await next_server_seq(session, user_id)
        await _create_allocations(
            session,
            user_id=user_id,
            budget_id=budget_id,
            currency=budget.currency,
            allocations=data.allocations,
        )
        changed["allocations"] = len(data.allocations)

    if changed:
        budget.version += 1
        budget.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="budget",
            entity_id=budget_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff=changed,
        )
        await session.flush()
    return budget


async def delete_budget(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    budget_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    budget = await repo.get(session, user_id, budget_id)
    if budget is None:
        raise NotFoundError("budget not found")
    budget.deleted_at = clock.now()
    budget.version += 1
    budget.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="budget",
        entity_id=budget_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()


async def get_status(
    session: AsyncSession, *, user_id: uuid.UUID, budget: Budget, as_of: dt.date, offset: int = 0
) -> BudgetStatus:
    start, end = period_bounds(budget, as_of, offset)
    start_dt = dt.datetime.combine(start, dt.time.min, tzinfo=dt.UTC)
    end_dt = dt.datetime.combine(end, dt.time.max, tzinfo=dt.UTC)
    records = await reporting_records(
        session, user_id, currency=budget.currency, date_from=start_dt, date_to=end_dt
    )
    spent_by_cat = {
        g.key: g.total.amount_minor for g in spending_by_category(records, budget.currency)
    }

    allocations = await repo.allocations(session, user_id, budget.id)
    category_lines = [
        assess_line(
            category_id=alloc.category_id,
            allocated=Money(alloc.amount_minor, budget.currency),
            spent=Money(spent_by_cat.get(alloc.category_id, 0), budget.currency),
            period_start=start,
            period_end=end,
            as_of=as_of,
        )
        for alloc in allocations
    ]

    overall_line: BudgetLineStatus | None = None
    if budget.overall_amount_minor is not None:
        overall_line = assess_line(
            category_id=None,
            allocated=Money(budget.overall_amount_minor, budget.currency),
            spent=total_spending(records, budget.currency),
            period_start=start,
            period_end=end,
            as_of=as_of,
        )

    rollup_lines = category_lines if category_lines else ([overall_line] if overall_line else [])
    all_lines = category_lines + ([overall_line] if overall_line else [])
    rollup = assess_budget(
        lines=rollup_lines, currency=budget.currency, period_start=start, period_end=end
    )
    return BudgetStatus(
        period_start=start,
        period_end=end,
        total_allocated=rollup.total_allocated,
        total_spent=rollup.total_spent,
        total_remaining=rollup.total_remaining,
        utilization_ratio=rollup.utilization_ratio,
        health=rollup.health,
        lines=tuple(all_lines),
    )


async def evaluate_alerts(
    session: AsyncSession, *, user_id: uuid.UUID, category_id: uuid.UUID, clock: Clock
) -> int:
    """Create budget alerts for any threshold crossed in the current period.

    Idempotent: at most one alert per (budget, period, category, level). Called by the
    TransactionCreated event handler (see app/events).
    """
    as_of = clock.now().date()
    created = 0
    for budget in await repo.budgets_for_category(session, user_id, category_id):
        status = await get_status(session, user_id=user_id, budget=budget, as_of=as_of)
        for line in status.lines:
            if line.category_id != category_id:
                continue
            level = _level_for(line.health)
            if level is None:
                continue
            if await repo.alert_exists(
                session, user_id, budget.id, status.period_start, category_id, level
            ):
                continue
            repo.add_alert(
                session,
                BudgetAlert(
                    id=new_id(),
                    user_id=user_id,
                    budget_id=budget.id,
                    period_start=status.period_start,
                    category_id=category_id,
                    level=level,
                ),
            )
            created += 1
    if created:
        await session.flush()
    return created


def _level_for(health: BudgetHealth) -> str | None:
    if health is BudgetHealth.OVER:
        return "over"
    if health is BudgetHealth.WARNING:
        return "warning"
    return None
