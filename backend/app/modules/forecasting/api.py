"""Forecast REST API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import MoneySchema
from app.domain.enums import ForecastHorizon
from app.modules.forecasting import service
from app.modules.forecasting.schemas import (
    BudgetExhaustionOut,
    ForecastPointOut,
    ForecastResponse,
    GoalCompletionOut,
)

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("", response_model=ForecastResponse)
async def forecast(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    horizon: ForecastHorizon = ForecastHorizon.D30,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> ForecastResponse:
    bundle = await service.build_forecast(
        session, user_id=user_id, currency=currency, horizon=horizon, clock=clock
    )
    cash = bundle.cash
    return ForecastResponse(
        horizon=horizon,
        currency=currency.upper(),
        starting_balance=MoneySchema.from_money(cash.starting_balance),
        ending_balance=MoneySchema.from_money(cash.ending_balance),
        min_balance=MoneySchema.from_money(cash.min_balance),
        min_balance_date=cash.min_balance_date,
        projected_negative=cash.projected_negative,
        total_inflows=MoneySchema.from_money(cash.total_inflows),
        total_outflows=MoneySchema.from_money(cash.total_outflows),
        daily_discretionary_minor=bundle.daily_discretionary_minor,
        timeline=[
            ForecastPointOut(date=p.date, balance=MoneySchema.from_money(p.balance))
            for p in cash.timeline
        ],
        assumptions=list(cash.assumptions),
        goal_completions=[
            GoalCompletionOut(
                goal_id=g.goal_id, name=g.name, projected_completion=g.projected_completion
            )
            for g in bundle.goal_completions
        ],
        budget_exhaustions=[
            BudgetExhaustionOut(
                budget_id=b.budget_id, name=b.name, projected_exhaustion=b.projected_exhaustion
            )
            for b in bundle.budget_exhaustions
        ],
        subscription_monthly=MoneySchema.from_money(bundle.subscription_monthly),
        subscription_annual=MoneySchema.from_money(bundle.subscription_annual),
    )
