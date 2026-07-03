"""User profile + financial preferences (one row per user).

Holds identity/locale settings and the financial-strategy preferences the future AI
copilot consumes. JIT-created on first access. Sync-ready via `SyncMixin`.
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin
from app.domain.enums import FinancialPriority, RiskProfile


class UserProfile(Base, SyncMixin):
    __tablename__ = "user_profiles"

    # One profile per user; the row id is distinct from user_id for sync uniformity.
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    locale: Mapped[str] = mapped_column(String(10), default="en-IN")
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    week_start_day: Mapped[int] = mapped_column(Integer, default=0)  # 0=Monday .. 6=Sunday
    monthly_income_minor: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Financial preferences (consumed by the AI copilot; never drive calculations).
    financial_priority: Mapped[FinancialPriority] = mapped_column(
        Enum(FinancialPriority, native_enum=False), default=FinancialPriority.BALANCED
    )
    risk_profile: Mapped[RiskProfile] = mapped_column(
        Enum(RiskProfile, native_enum=False), default=RiskProfile.MODERATE
    )
