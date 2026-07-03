"""Merchant request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class MerchantCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)


class MerchantUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)


class MerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    normalized_name: str
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime
