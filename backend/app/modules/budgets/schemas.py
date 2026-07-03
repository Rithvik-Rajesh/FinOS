"""Budget request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import CurrencyStr, MoneySchema
from app.domain.enums import BudgetHealth, BudgetPeriodType


class AllocationInput(BaseModel):
    category_id: uuid.UUID
    amount_minor: int = Field(ge=0)


class BudgetCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    period_type: BudgetPeriodType = BudgetPeriodType.MONTHLY
    currency: CurrencyStr
    overall_amount_minor: int | None = Field(default=None, ge=0)
    custom_period_days: int | None = Field(default=None, ge=1, le=366)
    allocations: list[AllocationInput] = Field(default_factory=list)


class BudgetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    overall_amount_minor: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    allocations: list[AllocationInput] | None = None  # replaces the set when provided


class BudgetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    period_type: BudgetPeriodType
    currency: str
    overall_amount_minor: int | None
    custom_period_days: int | None
    is_active: bool
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime


class BudgetLineStatusOut(BaseModel):
    category_id: uuid.UUID | None
    allocated: MoneySchema
    spent: MoneySchema
    remaining: MoneySchema
    utilization_ratio: float | None
    health: BudgetHealth
    projected_spend: MoneySchema | None
    projected_exhaustion: dt.date | None


class BudgetStatusOut(BaseModel):
    budget_id: uuid.UUID
    period_start: dt.date
    period_end: dt.date
    total_allocated: MoneySchema
    total_spent: MoneySchema
    total_remaining: MoneySchema
    utilization_ratio: float | None
    health: BudgetHealth
    lines: list[BudgetLineStatusOut]


class BudgetAlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    budget_id: uuid.UUID
    period_start: dt.date
    category_id: uuid.UUID | None
    level: str
    acknowledged: bool
    created_at: dt.datetime
