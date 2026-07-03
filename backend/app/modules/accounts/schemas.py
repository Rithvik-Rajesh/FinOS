"""Account request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import CurrencyStr, MoneySchema
from app.domain.enums import AccountType


class AccountCreate(BaseModel):
    id: uuid.UUID | None = None  # client may supply a UUIDv7 for offline creates
    name: str = Field(min_length=1, max_length=120)
    type: AccountType
    currency: CurrencyStr
    opening_balance_minor: int = 0
    institution: str | None = Field(default=None, max_length=120)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    is_archived: bool | None = None
    institution: str | None = Field(default=None, max_length=120)


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: AccountType
    currency: str
    opening_balance_minor: int
    is_archived: bool
    institution: str | None
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime


class AccountWithBalance(AccountOut):
    balance: MoneySchema


class ReconcileRequest(BaseModel):
    statement_balance: MoneySchema


class ReconcileResult(BaseModel):
    computed_balance: MoneySchema
    statement_balance: MoneySchema
    difference: MoneySchema  # statement - computed; zero means reconciled
