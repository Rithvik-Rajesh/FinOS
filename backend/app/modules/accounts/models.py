"""Account ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin
from app.domain.enums import AccountType


class Account(Base, SyncMixin):
    __tablename__ = "accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[AccountType] = mapped_column(Enum(AccountType, native_enum=False))
    currency: Mapped[str] = mapped_column(String(3))
    # Balance is derived (opening + sum of ledger entries); the opening balance seeds it.
    opening_balance_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    # Future bank-integration metadata (unused until Account Aggregator work).
    institution: Mapped[str | None] = mapped_column(String(120), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
