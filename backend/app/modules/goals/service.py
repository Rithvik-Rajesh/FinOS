"""Goal use cases: CRUD, contributions, milestones, and on-read projection.

Projection is computed deterministically from the contribution history via the pure
`app.domain.goals` engine — never stored, so it can never drift from the ledger of
contributions.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.goals import GoalProjection, project_goal
from app.domain.ids import new_id
from app.domain.money import Money
from app.modules.audit.repository import record as audit_record
from app.modules.goals import repository as repo
from app.modules.goals.models import Goal, GoalContribution, GoalMilestone
from app.modules.goals.schemas import ContributionCreate, GoalCreate, GoalUpdate, MilestoneCreate

# Contribution rate is observed over this trailing window (a quarter), then annualized
# to a monthly figure. Transparent and deterministic (see GOALS_ENGINE.md).
_OBSERVATION_DAYS = 90
_OBSERVATION_MONTHS = 3


async def create_goal(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: GoalCreate,
    correlation_id: str | None = None,
) -> Goal:
    goal_id = data.id or new_id()
    existing = await repo.get(session, user_id, goal_id)
    if existing is not None:
        return existing
    goal = Goal(
        id=goal_id,
        user_id=user_id,
        name=data.name,
        description=data.description,
        goal_type=data.goal_type,
        target_amount_minor=data.target_amount_minor,
        currency=data.currency.upper(),
        deadline=data.deadline,
        priority=data.priority,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, goal)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="goal",
        entity_id=goal_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name, "target_amount_minor": data.target_amount_minor},
    )
    await session.flush()
    return goal


async def update_goal(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    data: GoalUpdate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Goal:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    fields = data.model_dump(exclude_unset=True)
    changed: dict[str, object] = {}
    for key, value in fields.items():
        if getattr(goal, key) != value:
            setattr(goal, key, value)
            changed[key] = value
    from app.domain.enums import GoalStatus

    if data.status is GoalStatus.ARCHIVED and goal.archived_at is None:
        goal.archived_at = clock.now()
    if changed:
        goal.version += 1
        goal.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="goal",
            entity_id=goal_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff=changed,
        )
        await session.flush()
    return goal


async def delete_goal(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    goal.deleted_at = clock.now()
    goal.version += 1
    goal.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="goal",
        entity_id=goal_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()


async def add_contribution(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    data: ContributionCreate,
    clock: Clock,
    correlation_id: str | None = None,
) -> GoalContribution:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    money = data.amount.to_money()
    if money.currency != goal.currency:
        from app.core.errors import AppError

        raise AppError("contribution currency must match the goal currency")

    contribution = GoalContribution(
        id=data.id or new_id(),
        user_id=user_id,
        goal_id=goal_id,
        amount_minor=money.amount_minor,
        currency=money.currency,
        occurred_at=data.occurred_at or clock.now(),
        transaction_id=data.transaction_id,
        note=data.note,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add_contribution(session, contribution)
    await session.flush()

    await _reconcile_goal_state(session, user_id=user_id, goal=goal, clock=clock)
    audit_record(
        session,
        user_id=user_id,
        action="contribute",
        entity_type="goal",
        entity_id=goal_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"amount_minor": money.amount_minor},
    )
    await session.flush()
    return contribution


async def _reconcile_goal_state(
    session: AsyncSession, *, user_id: uuid.UUID, goal: Goal, clock: Clock
) -> None:
    """Mark reached milestones and flag the goal achieved when the target is hit."""
    from app.domain.enums import GoalStatus

    current = await repo.contributed_total(session, user_id, goal.id)
    now = clock.now()

    for milestone in await repo.list_milestones(session, user_id, goal.id):
        if milestone.reached_at is None and current >= milestone.target_amount_minor:
            milestone.reached_at = now
            milestone.version += 1
            milestone.server_seq = await next_server_seq(session, user_id)

    if goal.status is GoalStatus.ACTIVE and current >= goal.target_amount_minor:
        goal.status = GoalStatus.ACHIEVED
        goal.version += 1
        goal.server_seq = await next_server_seq(session, user_id)


async def add_milestone(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    data: MilestoneCreate,
    correlation_id: str | None = None,
) -> GoalMilestone:
    goal = await repo.get(session, user_id, goal_id)
    if goal is None:
        raise NotFoundError("goal not found")
    milestone = GoalMilestone(
        id=data.id or new_id(),
        user_id=user_id,
        goal_id=goal_id,
        name=data.name,
        target_amount_minor=data.target_amount_minor,
        currency=goal.currency,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add_milestone(session, milestone)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="goal_milestone",
        entity_id=milestone.id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name},
    )
    await session.flush()
    return milestone


async def get_projection(
    session: AsyncSession, *, user_id: uuid.UUID, goal: Goal, clock: Clock
) -> tuple[GoalProjection, Money]:
    current_minor = await repo.contributed_total(session, user_id, goal.id)
    since = clock.now() - dt.timedelta(days=_OBSERVATION_DAYS)
    recent = await repo.contributed_since(session, user_id, goal.id, since)
    observed_monthly = Money(recent // _OBSERVATION_MONTHS, goal.currency)

    projection = project_goal(
        target=Money(goal.target_amount_minor, goal.currency),
        current=Money(current_minor, goal.currency),
        deadline=goal.deadline,
        observed_monthly=observed_monthly,
        as_of=clock.now().date(),
    )
    return projection, Money(current_minor, goal.currency)
