"""Recurring series request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import MoneySchema
from app.domain.enums import (
    BillingCycle,
    OccurrenceStatus,
    RecurrenceInterval,
    RecurringDirection,
    RecurringKind,
    RecurringStatus,
)


class SeriesCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    kind: RecurringKind = RecurringKind.OTHER
    direction: RecurringDirection = RecurringDirection.OUTFLOW
    amount: MoneySchema
    interval: RecurrenceInterval = RecurrenceInterval.MONTHLY
    anchor_at: dt.datetime
    account_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    end_at: dt.datetime | None = None
    is_subscription: bool = False
    vendor: str | None = Field(default=None, max_length=160)
    billing_cycle: BillingCycle | None = None
    auto_renew: bool | None = None


class SeriesUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    amount: MoneySchema | None = None
    category_id: uuid.UUID | None = None
    status: RecurringStatus | None = None
    vendor: str | None = Field(default=None, max_length=160)
    auto_renew: bool | None = None
    end_at: dt.datetime | None = None


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    kind: RecurringKind
    direction: RecurringDirection
    amount_minor: int
    currency: str
    interval: RecurrenceInterval
    anchor_at: dt.datetime
    next_due_at: dt.datetime
    end_at: dt.datetime | None
    account_id: uuid.UUID | None
    category_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    status: RecurringStatus
    detected: bool
    confidence: int | None
    is_subscription: bool
    vendor: str | None
    billing_cycle: BillingCycle | None
    auto_renew: bool | None
    cancelled_at: dt.datetime | None
    version: int
    server_seq: int


class DetectedPatternOut(BaseModel):
    merchant_id: uuid.UUID | None
    amount: MoneySchema
    interval: RecurrenceInterval
    occurrences: int
    confidence: int
    first_seen: dt.datetime
    last_seen: dt.datetime
    expected_next: dt.datetime


class DetectResponse(BaseModel):
    created: list[SeriesOut]
    patterns: list[DetectedPatternOut]


class OccurrenceOut(BaseModel):
    series_id: uuid.UUID
    name: str
    due_at: dt.datetime
    amount: MoneySchema
    direction: RecurringDirection
    status: OccurrenceStatus


class UpcomingResponse(BaseModel):
    items: list[OccurrenceOut]
