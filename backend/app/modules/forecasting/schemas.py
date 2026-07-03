"""Forecast response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.api.schemas import MoneySchema
from app.domain.enums import ForecastHorizon


class ForecastPointOut(BaseModel):
    date: dt.date
    balance: MoneySchema


class GoalCompletionOut(BaseModel):
    goal_id: uuid.UUID
    name: str
    projected_completion: dt.date | None


class BudgetExhaustionOut(BaseModel):
    budget_id: uuid.UUID
    name: str
    projected_exhaustion: dt.date | None


class ForecastResponse(BaseModel):
    horizon: ForecastHorizon
    currency: str
    starting_balance: MoneySchema
    ending_balance: MoneySchema
    min_balance: MoneySchema
    min_balance_date: dt.date
    projected_negative: bool
    total_inflows: MoneySchema
    total_outflows: MoneySchema
    daily_discretionary_minor: int
    timeline: list[ForecastPointOut]
    assumptions: list[str]
    goal_completions: list[GoalCompletionOut]
    budget_exhaustions: list[BudgetExhaustionOut]
    subscription_monthly: MoneySchema
    subscription_annual: MoneySchema
