"""Profile & preferences schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import FinancialPriority, RiskProfile


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str | None
    currency: str
    locale: str
    timezone: str
    week_start_day: int
    monthly_income_minor: int | None
    financial_priority: FinancialPriority
    risk_profile: RiskProfile
    version: int
    server_seq: int
    updated_at: dt.datetime


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    locale: str | None = Field(default=None, max_length=10)
    timezone: str | None = Field(default=None, max_length=64)
    week_start_day: int | None = Field(default=None, ge=0, le=6)
    monthly_income_minor: int | None = Field(default=None, ge=0)


class PreferencesOut(BaseModel):
    financial_priority: FinancialPriority
    risk_profile: RiskProfile
    monthly_income_minor: int | None


class PreferencesUpdate(BaseModel):
    financial_priority: FinancialPriority | None = None
    risk_profile: RiskProfile | None = None
    monthly_income_minor: int | None = Field(default=None, ge=0)
