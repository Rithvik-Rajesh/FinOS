"""Recurring series ORM model.

One model powers recurring expenses, salary (inflow), and subscriptions — a subscription
is a `RecurringSeries` with `is_subscription=True` plus vendor/billing metadata (ADR-007).
Occurrences are computed on read from the recurrence engine, not stored.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin
from app.domain.enums import (
    BillingCycle,
    RecurrenceInterval,
    RecurringDirection,
    RecurringKind,
    RecurringStatus,
)


class RecurringSeries(Base, SyncMixin):
    __tablename__ = "recurring_series"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[RecurringKind] = mapped_column(Enum(RecurringKind, native_enum=False))
    direction: Mapped[RecurringDirection] = mapped_column(
        Enum(RecurringDirection, native_enum=False), default=RecurringDirection.OUTFLOW
    )
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    interval: Mapped[RecurrenceInterval] = mapped_column(
        Enum(RecurrenceInterval, native_enum=False)
    )
    anchor_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))  # a known occurrence
    next_due_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)

    status: Mapped[RecurringStatus] = mapped_column(
        Enum(RecurringStatus, native_enum=False), default=RecurringStatus.ACTIVE, index=True
    )
    # Detection provenance / approval workflow.
    detected: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–100 when detected

    # Subscription specialization.
    is_subscription: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    vendor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    billing_cycle: Mapped[BillingCycle | None] = mapped_column(
        Enum(BillingCycle, native_enum=False), nullable=True
    )
    auto_renew: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    cancelled_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
