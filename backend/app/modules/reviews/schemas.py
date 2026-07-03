"""Review response schemas."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.api.schemas import MoneySchema


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    period: str
    period_start: dt.date
    period_end: dt.date
    currency: str
    total_spent: MoneySchema
    total_income: MoneySchema
    net_cashflow: MoneySchema
    savings_rate_pct: Decimal | None
    payload: dict[str, Any]
    generated_at: dt.datetime

    @classmethod
    def from_model(cls, r: Any) -> ReviewOut:
        return cls(
            id=r.id,
            period=r.period.value,
            period_start=r.period_start,
            period_end=r.period_end,
            currency=r.currency,
            total_spent=MoneySchema(amount_minor=r.total_spent_minor, currency=r.currency),
            total_income=MoneySchema(amount_minor=r.total_income_minor, currency=r.currency),
            net_cashflow=MoneySchema(amount_minor=r.net_cashflow_minor, currency=r.currency),
            savings_rate_pct=(
                Decimal(r.savings_rate_bps) / 100 if r.savings_rate_bps is not None else None
            ),
            payload=r.payload,
            generated_at=r.generated_at,
        )
