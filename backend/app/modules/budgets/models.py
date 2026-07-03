"""Budget ORM models: Budget, BudgetCategoryAllocation, BudgetAlert.

Budget *periods* and *utilization* are computed on read from the ledger (never stored),
so they can never drift from actual spending (ADR-011). Only the budget definition,
its allocations, and generated alerts are persisted.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin, utcnow
from app.domain.enums import BudgetPeriodType
from app.domain.ids import new_id


class Budget(Base, SyncMixin):
    __tablename__ = "budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160))
    period_type: Mapped[BudgetPeriodType] = mapped_column(Enum(BudgetPeriodType, native_enum=False))
    currency: Mapped[str] = mapped_column(String(3))
    # For an overall (non-category) budget cap; None when purely category-based.
    overall_amount_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    custom_period_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class BudgetCategoryAllocation(Base, SyncMixin):
    __tablename__ = "budget_allocations"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    budget_id: Mapped[uuid.UUID] = mapped_column(index=True)
    category_id: Mapped[uuid.UUID] = mapped_column()
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))


class BudgetAlert(Base):
    """System-generated when spend crosses a threshold. Append-only, event-driven."""

    __tablename__ = "budget_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    budget_id: Mapped[uuid.UUID] = mapped_column(index=True)
    period_start: Mapped[dt.date] = mapped_column(Date)
    category_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    level: Mapped[str] = mapped_column(String(20))  # 'warning' | 'over'
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
