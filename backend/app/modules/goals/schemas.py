"""Goal request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import CurrencyStr, MoneySchema
from app.domain.enums import GoalHealth, GoalStatus, GoalType


class GoalCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    goal_type: GoalType = GoalType.SAVINGS
    target_amount_minor: int = Field(gt=0)
    currency: CurrencyStr
    deadline: dt.date | None = None
    priority: int = Field(default=3, ge=1, le=5)


class GoalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    target_amount_minor: int | None = Field(default=None, gt=0)
    deadline: dt.date | None = None
    priority: int | None = Field(default=None, ge=1, le=5)
    status: GoalStatus | None = None


class GoalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    goal_type: GoalType
    target_amount_minor: int
    currency: str
    deadline: dt.date | None
    priority: int
    status: GoalStatus
    archived_at: dt.datetime | None
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime


class ContributionCreate(BaseModel):
    id: uuid.UUID | None = None
    amount: MoneySchema
    occurred_at: dt.datetime | None = None  # defaults to now
    transaction_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)


class ContributionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    amount_minor: int
    currency: str
    occurred_at: dt.datetime
    transaction_id: uuid.UUID | None
    note: str | None


class MilestoneCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=160)
    target_amount_minor: int = Field(gt=0)


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    goal_id: uuid.UUID
    name: str
    target_amount_minor: int
    currency: str
    reached_at: dt.datetime | None


class GoalProjectionOut(BaseModel):
    goal_id: uuid.UUID
    target: MoneySchema
    current: MoneySchema
    remaining: MoneySchema
    progress_ratio: float
    required_monthly: MoneySchema | None
    observed_monthly: MoneySchema
    projected_completion: dt.date | None
    months_to_deadline: int | None
    health: GoalHealth
    percent_complete: Decimal
