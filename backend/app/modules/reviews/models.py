"""Review snapshot model — stored for historical viewing.

Reviews are generated from the deterministic engines and persisted so a user can browse
past weeks/months. Key metrics are columns (for listing); the full computed breakdown is
the JSON `payload`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import BigInteger, Date, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, utcnow
from app.domain.enums import ReviewPeriod
from app.domain.ids import new_id


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "period", "period_start", name="uq_review_period"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    period: Mapped[ReviewPeriod] = mapped_column(Enum(ReviewPeriod, native_enum=False), index=True)
    period_start: Mapped[dt.date] = mapped_column(Date, index=True)
    period_end: Mapped[dt.date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    total_spent_minor: Mapped[int] = mapped_column(BigInteger)
    total_income_minor: Mapped[int] = mapped_column(BigInteger)
    net_cashflow_minor: Mapped[int] = mapped_column(BigInteger)
    savings_rate_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)  # pct × 100
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
