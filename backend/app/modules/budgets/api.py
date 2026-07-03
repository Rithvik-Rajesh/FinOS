"""Budgets REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import MoneySchema, Page
from app.core.errors import NotFoundError
from app.domain.budgets import BudgetStatus
from app.modules.budgets import repository as repo
from app.modules.budgets import service
from app.modules.budgets.schemas import (
    BudgetAlertOut,
    BudgetCreate,
    BudgetLineStatusOut,
    BudgetOut,
    BudgetStatusOut,
    BudgetUpdate,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _status_out(budget_id: uuid.UUID, s: BudgetStatus) -> BudgetStatusOut:
    return BudgetStatusOut(
        budget_id=budget_id,
        period_start=s.period_start,
        period_end=s.period_end,
        total_allocated=MoneySchema.from_money(s.total_allocated),
        total_spent=MoneySchema.from_money(s.total_spent),
        total_remaining=MoneySchema.from_money(s.total_remaining),
        utilization_ratio=s.utilization_ratio,
        health=s.health,
        lines=[
            BudgetLineStatusOut(
                category_id=line.category_id,
                allocated=MoneySchema.from_money(line.allocated),
                spent=MoneySchema.from_money(line.spent),
                remaining=MoneySchema.from_money(line.remaining),
                utilization_ratio=line.utilization_ratio,
                health=line.health,
                projected_spend=(
                    MoneySchema.from_money(line.projected_spend)
                    if line.projected_spend is not None
                    else None
                ),
                projected_exhaustion=line.projected_exhaustion,
            )
            for line in s.lines
        ],
    )


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
async def create_budget(
    body: BudgetCreate, session: DbSession, user_id: CurrentUserId, correlation_id: CorrelationId
) -> BudgetOut:
    budget = await service.create_budget(
        session, user_id=user_id, data=body, correlation_id=correlation_id
    )
    return BudgetOut.model_validate(budget)


@router.get("", response_model=Page[BudgetOut])
async def list_budgets(
    session: DbSession,
    user_id: CurrentUserId,
    active_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BudgetOut]:
    rows = await repo.list_(session, user_id, active_only=active_only, limit=limit, offset=offset)
    return Page(items=[BudgetOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.get("/alerts", response_model=Page[BudgetAlertOut])
async def list_alerts(
    session: DbSession,
    user_id: CurrentUserId,
    budget_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[BudgetAlertOut]:
    rows = await repo.list_alerts(session, user_id, budget_id=budget_id, limit=limit, offset=offset)
    return Page(items=[BudgetAlertOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.get("/{budget_id}", response_model=BudgetOut)
async def get_budget(budget_id: uuid.UUID, session: DbSession, user_id: CurrentUserId) -> BudgetOut:
    budget = await repo.get(session, user_id, budget_id)
    if budget is None:
        raise NotFoundError("budget not found")
    return BudgetOut.model_validate(budget)


@router.patch("/{budget_id}", response_model=BudgetOut)
async def update_budget(
    budget_id: uuid.UUID,
    body: BudgetUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> BudgetOut:
    budget = await service.update_budget(
        session,
        user_id=user_id,
        budget_id=budget_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return BudgetOut.model_validate(budget)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_budget(
        session, user_id=user_id, budget_id=budget_id, clock=clock, correlation_id=correlation_id
    )


@router.get("/{budget_id}/status", response_model=BudgetStatusOut)
async def get_status(
    budget_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    period_offset: Annotated[int, Query(ge=-24, le=0)] = 0,
) -> BudgetStatusOut:
    """Budget utilization for the current period, or a past one via `period_offset`."""
    budget = await repo.get(session, user_id, budget_id)
    if budget is None:
        raise NotFoundError("budget not found")
    s = await service.get_status(
        session, user_id=user_id, budget=budget, as_of=clock.now().date(), offset=period_offset
    )
    return _status_out(budget_id, s)
