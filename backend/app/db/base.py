"""SQLAlchemy declarative base and the shared mixins every user-owned table uses.

See docs/DATABASE.md. `SyncMixin` + `AuditMixin` provide the columns that make
offline sync, soft-delete, and auditing uniform across the schema.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SyncMixin(TimestampMixin):
    """Columns that power the delta-sync protocol (docs/API.md#sync-protocol)."""

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # UUIDv7, client-generatable
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Assigned server-side from a per-user monotonic sequence; the sync cursor.
    server_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Soft delete / tombstone; default queries exclude non-null rows.
    deleted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
