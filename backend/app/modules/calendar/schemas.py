"""Financial calendar schemas (events are computed, never stored)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel

from app.api.schemas import MoneySchema
from app.domain.enums import FinancialEventType


class FinancialEventOut(BaseModel):
    type: FinancialEventType
    title: str
    occurs_at: dt.datetime
    amount: MoneySchema | None
    direction: str  # 'inflow' | 'outflow' | 'neutral'
    source_kind: str
    source_id: uuid.UUID | None


class CalendarResponse(BaseModel):
    start: dt.date
    end: dt.date
    events: list[FinancialEventOut]
    upcoming_outflow: MoneySchema
    upcoming_inflow: MoneySchema
