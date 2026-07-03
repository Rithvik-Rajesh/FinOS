"""Goal ORM models: Goal, GoalContribution, GoalMilestone.

`SyncMixin` makes these sync-ready (id/version/server_seq/deleted_at); wiring them into
the delta-sync registry is a mechanical follow-up (see ADR-011). Projections are computed
on read, never stored.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, Date, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin
from app.domain.enums import GoalStatus, GoalType


class Goal(Base, SyncMixin):
    __tablename__ = "goals"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    goal_type: Mapped[GoalType] = mapped_column(Enum(GoalType, native_enum=False))
    target_amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    deadline: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1 (highest) .. 5
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus, native_enum=False), default=GoalStatus.ACTIVE, index=True
    )
    archived_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GoalContribution(Base, SyncMixin):
    __tablename__ = "goal_contributions"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    goal_id: Mapped[uuid.UUID] = mapped_column(index=True)
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), index=True)
    # Optional link to the transfer transaction that funded this contribution.
    transaction_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class GoalMilestone(Base, SyncMixin):
    __tablename__ = "goal_milestones"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    goal_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(160))
    target_amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    reached_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
