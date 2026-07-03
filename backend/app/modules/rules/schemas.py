"""Rule request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RuleField, RuleLogic, RuleOperator, TransactionType

PredicateValue = int | str | bool | list[int] | list[str]


class PredicateSchema(BaseModel):
    field: RuleField
    operator: RuleOperator
    value: PredicateValue


class RuleCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    priority: int = Field(default=100, ge=0)
    logic: RuleLogic = RuleLogic.ALL
    conditions: list[PredicateSchema] = Field(min_length=1)
    set_category_id: uuid.UUID | None = None
    set_merchant_id: uuid.UUID | None = None
    tags: list[str] = Field(default_factory=list)
    stop_processing: bool = False
    is_active: bool = True


class RuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    priority: int | None = Field(default=None, ge=0)
    logic: RuleLogic | None = None
    conditions: list[PredicateSchema] | None = None
    set_category_id: uuid.UUID | None = None
    set_merchant_id: uuid.UUID | None = None
    tags: list[str] | None = None
    stop_processing: bool | None = None
    is_active: bool | None = None


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    priority: int
    logic: RuleLogic
    conditions: list[PredicateSchema]
    set_category_id: uuid.UUID | None
    set_merchant_id: uuid.UUID | None
    tags: list[str]
    stop_processing: bool
    is_active: bool
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime


class FactsSchema(BaseModel):
    """Sample transaction facts for testing a rule."""

    type: TransactionType
    amount_minor: int
    currency: str = "INR"
    hour_of_day: int = Field(default=12, ge=0, le=23)
    day_of_week: int = Field(default=0, ge=0, le=6)
    merchant_name: str | None = None
    counterparty: str | None = None
    account_name: str | None = None
    note: str | None = None


class RuleTestRequest(BaseModel):
    rule: RuleCreate
    facts: FactsSchema


class RuleTestResponse(BaseModel):
    matches: bool


class RuleSimulateRequest(BaseModel):
    draft_rule: RuleCreate | None = None  # simulate active rules, optionally plus a draft
    limit: int = Field(default=200, ge=1, le=1000)


class SimulatedChange(BaseModel):
    transaction_id: uuid.UUID
    current_category_id: uuid.UUID | None
    proposed_category_id: uuid.UUID | None
    changed: bool


class RuleSimulateResponse(BaseModel):
    evaluated: int
    changed: int
    changes: list[SimulatedChange]
