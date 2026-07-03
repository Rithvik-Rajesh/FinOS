"""Budget data access — tenant-scoped."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.budgets.models import Budget, BudgetAlert, BudgetCategoryAllocation


async def get(session: AsyncSession, user_id: uuid.UUID, budget_id: uuid.UUID) -> Budget | None:
    stmt = select(Budget).where(
        Budget.id == budget_id, Budget.user_id == user_id, Budget.deleted_at.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    active_only: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Budget]:
    stmt = (
        select(Budget)
        .where(Budget.user_id == user_id, Budget.deleted_at.is_(None))
        .order_by(Budget.created_at)
        .limit(limit)
        .offset(offset)
    )
    if active_only:
        stmt = stmt.where(Budget.is_active.is_(True))
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, budget: Budget) -> None:
    session.add(budget)


async def allocations(
    session: AsyncSession, user_id: uuid.UUID, budget_id: uuid.UUID
) -> Sequence[BudgetCategoryAllocation]:
    stmt = select(BudgetCategoryAllocation).where(
        BudgetCategoryAllocation.user_id == user_id,
        BudgetCategoryAllocation.budget_id == budget_id,
        BudgetCategoryAllocation.deleted_at.is_(None),
    )
    return (await session.execute(stmt)).scalars().all()


async def budgets_for_category(
    session: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID
) -> Sequence[Budget]:
    """Active budgets that allocate to a category (used by the event handler)."""
    stmt = (
        select(Budget)
        .join(BudgetCategoryAllocation, BudgetCategoryAllocation.budget_id == Budget.id)
        .where(
            Budget.user_id == user_id,
            Budget.is_active.is_(True),
            Budget.deleted_at.is_(None),
            BudgetCategoryAllocation.category_id == category_id,
            BudgetCategoryAllocation.deleted_at.is_(None),
        )
        .distinct()
    )
    return (await session.execute(stmt)).scalars().all()


def add_allocation(session: AsyncSession, allocation: BudgetCategoryAllocation) -> None:
    session.add(allocation)


def add_alert(session: AsyncSession, alert: BudgetAlert) -> None:
    session.add(alert)


async def alert_exists(
    session: AsyncSession,
    user_id: uuid.UUID,
    budget_id: uuid.UUID,
    period_start: dt.date,
    category_id: uuid.UUID | None,
    level: str,
) -> bool:
    stmt = select(BudgetAlert.id).where(
        BudgetAlert.user_id == user_id,
        BudgetAlert.budget_id == budget_id,
        BudgetAlert.period_start == period_start,
        BudgetAlert.level == level,
        BudgetAlert.category_id.is_(None)
        if category_id is None
        else BudgetAlert.category_id == category_id,
    )
    return (await session.execute(stmt)).first() is not None


async def list_alerts(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    budget_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[BudgetAlert]:
    stmt = (
        select(BudgetAlert)
        .where(BudgetAlert.user_id == user_id)
        .order_by(BudgetAlert.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if budget_id is not None:
        stmt = stmt.where(BudgetAlert.budget_id == budget_id)
    return (await session.execute(stmt)).scalars().all()
