"""Category request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    icon: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=9)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    parent_id: uuid.UUID | None = None
    icon: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=9)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    parent_id: uuid.UUID | None
    icon: str | None
    color: str | None
    is_system: bool
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime
