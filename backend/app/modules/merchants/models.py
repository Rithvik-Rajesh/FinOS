"""Merchant ORM model — normalized payees/merchants (Swiggy, "Mom", Netflix)."""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin


class Merchant(Base, SyncMixin):
    __tablename__ = "merchants"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(200))
    # Case-folded name for dedup and rule matching; set by the service.
    normalized_name: Mapped[str] = mapped_column(String(200), index=True)
