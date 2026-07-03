"""Goal data access — tenant-scoped."""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import GoalStatus
from app.modules.goals.models import Goal, GoalContribution, GoalMilestone


async def get(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> Goal | None:
    stmt = select(Goal).where(
        Goal.id == goal_id, Goal.user_id == user_id, Goal.deleted_at.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: GoalStatus | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Goal]:
    stmt = (
        select(Goal)
        .where(Goal.user_id == user_id, Goal.deleted_at.is_(None))
        .order_by(Goal.priority, Goal.created_at)
        .limit(limit)
        .offset(offset)
    )
    if status is not None:
        stmt = stmt.where(Goal.status == status)
    return (await session.execute(stmt)).scalars().all()


def add(session: AsyncSession, goal: Goal) -> None:
    session.add(goal)


async def contributed_total(session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID) -> int:
    stmt = select(func.coalesce(func.sum(GoalContribution.amount_minor), 0)).where(
        GoalContribution.user_id == user_id,
        GoalContribution.goal_id == goal_id,
        GoalContribution.deleted_at.is_(None),
    )
    return int((await session.execute(stmt)).scalar_one())


async def contributed_since(
    session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID, since: dt.datetime
) -> int:
    stmt = select(func.coalesce(func.sum(GoalContribution.amount_minor), 0)).where(
        GoalContribution.user_id == user_id,
        GoalContribution.goal_id == goal_id,
        GoalContribution.deleted_at.is_(None),
        GoalContribution.occurred_at >= since,
    )
    return int((await session.execute(stmt)).scalar_one())


async def list_contributions(
    session: AsyncSession,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    *,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[GoalContribution]:
    stmt = (
        select(GoalContribution)
        .where(
            GoalContribution.user_id == user_id,
            GoalContribution.goal_id == goal_id,
            GoalContribution.deleted_at.is_(None),
        )
        .order_by(GoalContribution.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return (await session.execute(stmt)).scalars().all()


def add_contribution(session: AsyncSession, contribution: GoalContribution) -> None:
    session.add(contribution)


async def list_milestones(
    session: AsyncSession, user_id: uuid.UUID, goal_id: uuid.UUID
) -> Sequence[GoalMilestone]:
    stmt = (
        select(GoalMilestone)
        .where(
            GoalMilestone.user_id == user_id,
            GoalMilestone.goal_id == goal_id,
            GoalMilestone.deleted_at.is_(None),
        )
        .order_by(GoalMilestone.target_amount_minor)
    )
    return (await session.execute(stmt)).scalars().all()


def add_milestone(session: AsyncSession, milestone: GoalMilestone) -> None:
    session.add(milestone)
