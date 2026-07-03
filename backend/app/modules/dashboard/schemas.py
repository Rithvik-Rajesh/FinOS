"""Dashboard response schemas — one payload for the home screen.

Spending slices return ids (not names): the offline-first client already holds the
category/merchant catalog locally and maps names, so the dashboard avoids N+1 name joins.
"""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.api.schemas import MoneySchema
from app.domain.enums import ForecastHorizon, GoalHealth
from app.modules.insights.schemas import InsightOut


class OverviewSection(BaseModel):
    current_balance: MoneySchema
    net_cashflow: MoneySchema
    savings_rate_pct: Decimal | None
    active_goals: int
    avg_goal_progress: float


class SpendingSlice(BaseModel):
    key: uuid.UUID | None
    total: MoneySchema
    count: int


class UpcomingItem(BaseModel):
    type: str
    title: str
    occurs_at: dt.datetime
    amount: MoneySchema | None
    direction: str


class DashboardGoal(BaseModel):
    goal_id: uuid.UUID
    name: str
    progress_ratio: float
    health: GoalHealth
    target: MoneySchema
    current: MoneySchema
    projected_completion: dt.date | None


class ForecastPoint(BaseModel):
    date: dt.date
    balance: MoneySchema


class ForecastSection(BaseModel):
    horizon: ForecastHorizon
    ending_balance: MoneySchema
    min_balance: MoneySchema
    min_balance_date: dt.date
    projected_negative: bool
    timeline: list[ForecastPoint]


class DashboardResponse(BaseModel):
    currency: str
    generated_at: dt.datetime
    overview: OverviewSection
    insights: list[InsightOut]
    upcoming: list[UpcomingItem]
    goals: list[DashboardGoal]
    spending_by_category: list[SpendingSlice]
    spending_by_merchant: list[SpendingSlice]
    forecast: ForecastSection
