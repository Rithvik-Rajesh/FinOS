"""Insight response schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel

from app.api.schemas import MoneySchema
from app.domain.enums import InsightCategory, InsightSeverity
from app.domain.insights import Insight


class InsightOut(BaseModel):
    category: InsightCategory
    severity: InsightSeverity
    title: str
    detail: str
    metric: MoneySchema | None
    change_pct: Decimal | None
    data: dict[str, Any]

    @classmethod
    def from_domain(cls, insight: Insight) -> InsightOut:
        return cls(
            category=insight.category,
            severity=insight.severity,
            title=insight.title,
            detail=insight.detail,
            metric=MoneySchema.from_money(insight.metric) if insight.metric is not None else None,
            change_pct=insight.change_pct,
            data=insight.data,
        )


class InsightsResponse(BaseModel):
    items: list[InsightOut]
