"""Notification models: NotificationRule (what to notify), NotificationPreference (how to
deliver), NotificationEvent (the queue).

Event-driven and vendor-neutral: events are enqueued into `notification_events` with a
`channel`; concrete delivery (in-app now, push/email later) is a swappable notifier behind
a protocol — no vendor is baked into the schema (see NOTIFICATION_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, utcnow
from app.domain.enums import NotificationChannel, NotificationStatus, NotificationType
from app.domain.ids import new_id


class NotificationRule(Base):
    """What to notify about, and thresholds — one row per (user, type)."""

    __tablename__ = "notification_rules"
    __table_args__ = (UniqueConstraint("user_id", "type", name="uq_notif_rule"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lead_time_days: Mapped[int] = mapped_column(Integer, default=3)  # for reminders/bills
    params: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class NotificationPreference(Base):
    """How to deliver — one row per user (channel toggles + quiet hours)."""

    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(unique=True, index=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0–23
    quiet_hours_end: Mapped[int | None] = mapped_column(Integer, nullable=True)


class NotificationEvent(Base):
    """A queued notification (idempotent per `dedupe_key`)."""

    __tablename__ = "notification_events"
    __table_args__ = (UniqueConstraint("user_id", "dedupe_key", name="uq_notif_event"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, native_enum=False))
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False), default=NotificationChannel.IN_APP
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(1000))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus, native_enum=False), default=NotificationStatus.QUEUED, index=True
    )
    dedupe_key: Mapped[str] = mapped_column(String(200))
    scheduled_for: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
