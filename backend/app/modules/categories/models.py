"""Category ORM model — hierarchical spend/income categories."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin


class Category(Base, SyncMixin):
    __tablename__ = "categories"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
    icon: Mapped[str | None] = mapped_column(String(60), nullable=True)
    color: Mapped[str | None] = mapped_column(String(9), nullable=True)  # #RRGGBB[AA]
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
