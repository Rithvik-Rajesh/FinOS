"""Simulation (financial decision) schemas."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.api.schemas import MoneySchema


class EmiPlanOut(BaseModel):
    principal: MoneySchema
    annual_rate_bps: int
    months: int
    monthly_payment: MoneySchema
    total_payment: MoneySchema
    total_interest: MoneySchema


class EmiSimRequest(BaseModel):
    principal: MoneySchema
    annual_rate_bps: int = Field(ge=0, le=100000)
    months: int = Field(ge=1, le=600)


class GoalImpactOut(BaseModel):
    goal_id: uuid.UUID
    name: str
    baseline_completion: dt.date | None
    impacted_completion: dt.date | None
    delay_months: int | None


class PurchaseSimRequest(BaseModel):
    amount: MoneySchema
    funding: Literal["cash", "emi"] = "cash"
    emi_annual_rate_bps: int | None = Field(default=None, ge=0, le=100000)
    emi_months: int | None = Field(default=None, ge=1, le=600)


class PurchaseSimResponse(BaseModel):
    amount: MoneySchema
    funding: Literal["cash", "emi"]
    cash_before: MoneySchema
    cash_after: MoneySchema
    affordable_from_cash: bool
    emergency_floor: MoneySchema
    monthly_surplus_before: MoneySchema
    monthly_surplus_after: MoneySchema
    goal_impacts: list[GoalImpactOut]
    emi: EmiPlanOut | None
