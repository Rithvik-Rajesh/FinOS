"""Goals REST API."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import MoneySchema, Page
from app.core.errors import NotFoundError
from app.domain.enums import GoalStatus
from app.modules.goals import repository as repo
from app.modules.goals import service
from app.modules.goals.schemas import (
    ContributionCreate,
    ContributionOut,
    GoalCreate,
    GoalOut,
    GoalProjectionOut,
    GoalUpdate,
    MilestoneCreate,
    MilestoneOut,
)

router = APIRouter(prefix="/goals", tags=["goals"])


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
async def create_goal(
    body: GoalCreate, session: DbSession, user_id: CurrentUserId, correlation_id: CorrelationId
) -> GoalOut:
    goal = await service.create_goal(
        session, user_id=user_id, data=body, correlation_id=correlation_id
    )
    return GoalOut.model_validate(goal)


@router.get("", response_model=Page[GoalOut])
async def list_goals(
    session: DbSession,
    user_id: CurrentUserId,
    status_filter: Annotated[GoalStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[GoalOut]:
    rows = await repo.list_(session, user_id, status=status_filter, limit=limit, offset=offset)
    return Page(items=[GoalOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.get("/{goal_id}", response_model=GoalOut)
async def get_goal(goal_id: uuid.UUID, session: DbSession, user_id: CurrentUserId) -> GoalOut:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    return GoalOut.model_validate(goal)


@router.patch("/{goal_id}", response_model=GoalOut)
async def update_goal(
    goal_id: uuid.UUID,
    body: GoalUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> GoalOut:
    goal = await service.update_goal(
        session,
        user_id=user_id,
        goal_id=goal_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return GoalOut.model_validate(goal)


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_goal(
    goal_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_goal(
        session, user_id=user_id, goal_id=goal_id, clock=clock, correlation_id=correlation_id
    )


@router.post("/{goal_id}/contributions", response_model=ContributionOut, status_code=201)
async def add_contribution(
    goal_id: uuid.UUID,
    body: ContributionCreate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> ContributionOut:
    c = await service.add_contribution(
        session,
        user_id=user_id,
        goal_id=goal_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return ContributionOut.model_validate(c)


@router.get("/{goal_id}/contributions", response_model=Page[ContributionOut])
async def list_contributions(
    goal_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ContributionOut]:
    rows = await repo.list_contributions(session, user_id, goal_id, limit=limit, offset=offset)
    return Page(
        items=[ContributionOut.model_validate(r) for r in rows], has_more=len(rows) == limit
    )


@router.post("/{goal_id}/milestones", response_model=MilestoneOut, status_code=201)
async def add_milestone(
    goal_id: uuid.UUID,
    body: MilestoneCreate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> MilestoneOut:
    m = await service.add_milestone(
        session, user_id=user_id, goal_id=goal_id, data=body, correlation_id=correlation_id
    )
    return MilestoneOut.model_validate(m)


@router.get("/{goal_id}/milestones", response_model=list[MilestoneOut])
async def list_milestones(
    goal_id: uuid.UUID, session: DbSession, user_id: CurrentUserId
) -> list[MilestoneOut]:
    rows = await repo.list_milestones(session, user_id, goal_id)
    return [MilestoneOut.model_validate(r) for r in rows]


@router.get("/{goal_id}/projection", response_model=GoalProjectionOut)
async def get_projection(
    goal_id: uuid.UUID, session: DbSession, user_id: CurrentUserId, clock: ClockDep
) -> GoalProjectionOut:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    projection, _ = await service.get_projection(session, user_id=user_id, goal=goal, clock=clock)
    return GoalProjectionOut(
        goal_id=goal_id,
        target=MoneySchema.from_money(projection.target),
        current=MoneySchema.from_money(projection.current),
        remaining=MoneySchema.from_money(projection.remaining),
        progress_ratio=projection.progress_ratio,
        required_monthly=(
            MoneySchema.from_money(projection.required_monthly)
            if projection.required_monthly is not None
            else None
        ),
        observed_monthly=MoneySchema.from_money(projection.observed_monthly),
        projected_completion=projection.projected_completion,
        months_to_deadline=projection.months_to_deadline,
        health=projection.health,
        percent_complete=Decimal(str(round(projection.progress_ratio * 100, 1))),
    )
