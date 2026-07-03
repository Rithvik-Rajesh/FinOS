"""Subscription analytics schemas (subscriptions are recurring series)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.api.schemas import MoneySchema


class SubscriptionSummaryOut(BaseModel):
    currency: str
    active_count: int
    monthly: MoneySchema
    annual: MoneySchema


class InactiveSubscriptionOut(BaseModel):
    series_id: uuid.UUID
    name: str
    last_seen: dt.datetime | None
    days_inactive: int | None  # None when never seen in the ledger


class InactiveResponse(BaseModel):
    items: list[InactiveSubscriptionOut]


class RenewalOut(BaseModel):
    series_id: uuid.UUID
    name: str
    next_due_at: dt.datetime
    amount: MoneySchema


class RenewalsResponse(BaseModel):
    items: list[RenewalOut]
