"""Notification schemas."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import NotificationChannel, NotificationStatus, NotificationType


class NotificationRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    enabled: bool
    lead_time_days: int
    params: dict[str, Any]


class NotificationRuleUpdate(BaseModel):
    enabled: bool | None = None
    lead_time_days: int | None = Field(default=None, ge=0, le=60)


class PreferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    in_app_enabled: bool
    push_enabled: bool
    email_enabled: bool
    quiet_hours_start: int | None
    quiet_hours_end: int | None


class PreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    push_enabled: bool | None = None
    email_enabled: bool | None = None
    quiet_hours_start: int | None = Field(default=None, ge=0, le=23)
    quiet_hours_end: int | None = Field(default=None, ge=0, le=23)


class NotificationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    channel: NotificationChannel
    title: str
    body: str
    data: dict[str, Any]
    status: NotificationStatus
    created_at: dt.datetime
    read_at: dt.datetime | None


class ScanResponse(BaseModel):
    created: int
