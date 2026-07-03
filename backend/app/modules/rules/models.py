"""Categorization rule ORM model.

The rule's predicates and tags are stored as JSON (a small, versioned condition/action
DSL — never executable code). The engine that evaluates them is pure and lives in
`app.domain.rules`; this model is only persistence.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, SyncMixin
from app.domain.enums import RuleLogic


class CategorizationRule(Base, SyncMixin):
    __tablename__ = "categorization_rules"

    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str] = mapped_column(String(120))
    priority: Mapped[int] = mapped_column(Integer, index=True)
    logic: Mapped[RuleLogic] = mapped_column(
        Enum(RuleLogic, native_enum=False), default=RuleLogic.ALL
    )
    conditions: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    set_category_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    set_merchant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    stop_processing: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
