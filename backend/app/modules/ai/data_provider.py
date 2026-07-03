"""AssistantDataProvider — gathers deterministic engine outputs for the copilot.

Reads only; performs no arithmetic. Every number originates in a deterministic engine
(insights, forecast, goals, budgets, subscriptions, reviews).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.budgets import BudgetStatus
from app.domain.clock import Clock
from app.domain.enums import ForecastHorizon, GoalStatus
from app.domain.goals import GoalProjection
from app.domain.insights import Insight
from app.domain.money import Money
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.budgets.models import Budget
from app.modules.forecasting import service as forecasting_service
from app.modules.forecasting.service import ForecastBundle
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.goals.models import Goal
from app.modules.identity import service as identity_service
from app.modules.identity.models import UserProfile
from app.modules.insights import service as insights_service
from app.modules.reviews import repository as reviews_repo
from app.modules.reviews.models import Review
from app.modules.subscriptions import service as subscriptions_service


@dataclass(frozen=True, slots=True)
class AssistantData:
    currency: str
    profile: UserProfile
    insights: list[Insight]
    forecast: ForecastBundle
    goal_projections: list[tuple[Goal, GoalProjection, Money]]
    budget_statuses: list[tuple[Budget, BudgetStatus]]
    subscription_monthly: Money
    reviews: Sequence[Review]


class AssistantDataProvider:
    async def gather(
        self, session: AsyncSession, *, user_id: uuid.UUID, currency: str, clock: Clock
    ) -> AssistantData:
        currency = currency.upper()
        profile = await identity_service.get_or_create(session, user_id=user_id)
        insights = await insights_service.generate(
            session, user_id=user_id, currency=currency, clock=clock
        )
        forecast = await forecasting_service.build_forecast(
            session, user_id=user_id, currency=currency, horizon=ForecastHorizon.D30, clock=clock
        )

        goal_projections: list[tuple[Goal, GoalProjection, Money]] = []
        for goal in await goals_repo.list_(session, user_id, status=GoalStatus.ACTIVE, limit=50):
            if goal.currency != currency:
                continue
            projection, current = await goals_service.get_projection(
                session, user_id=user_id, goal=goal, clock=clock
            )
            goal_projections.append((goal, projection, current))

        budget_statuses: list[tuple[Budget, BudgetStatus]] = []
        for budget in await budgets_repo.list_(session, user_id, active_only=True, limit=50):
            if budget.currency != currency:
                continue
            status = await budgets_service.get_status(
                session, user_id=user_id, budget=budget, as_of=clock.now().date()
            )
            budget_statuses.append((budget, status))

        cost, _ = await subscriptions_service.summary(session, user_id=user_id, currency=currency)
        reviews = await reviews_repo.list_(session, user_id, limit=3)

        return AssistantData(
            currency=currency,
            profile=profile,
            insights=insights,
            forecast=forecast,
            goal_projections=goal_projections,
            budget_statuses=budget_statuses,
            subscription_monthly=cost.monthly,
            reviews=reviews,
        )
