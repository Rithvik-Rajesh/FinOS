"""Reporting response schemas."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.api.schemas import MoneySchema


class GroupTotalOut(BaseModel):
    key: uuid.UUID | None  # category_id or merchant_id (null = uncategorized)
    total: MoneySchema
    count: int


class PeriodTotalOut(BaseModel):
    period_start: dt.date
    total: MoneySchema
    count: int


class SummaryOut(BaseModel):
    currency: str
    spending: MoneySchema
    income: MoneySchema
    net: MoneySchema


class GrowthOut(BaseModel):
    current: MoneySchema
    previous: MoneySchema
    delta: MoneySchema
    pct_change: Decimal | None
    is_new: bool
