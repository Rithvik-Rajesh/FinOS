"""Transaction request/response schemas."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas import MoneySchema
from app.domain.enums import (
    CategorizationSource,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from app.modules.ledger.models import Transaction


class TransactionCreate(BaseModel):
    id: uuid.UUID | None = None  # client-supplied UUIDv7 for offline creates
    account_id: uuid.UUID
    type: TransactionType
    amount: MoneySchema
    occurred_at: dt.datetime
    counter_account_id: uuid.UUID | None = None  # required for transfers
    category_id: uuid.UUID | None = None  # if omitted, rules may assign one
    merchant_id: uuid.UUID | None = None
    counterparty: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    status: TransactionStatus = TransactionStatus.CLEARED
    source: TransactionSource = TransactionSource.MANUAL
    external_ref: str | None = Field(default=None, max_length=200)
    related_transaction_id: uuid.UUID | None = None


class TransactionUpdate(BaseModel):
    # Money-affecting fields (trigger a repost of ledger entries).
    account_id: uuid.UUID | None = None
    type: TransactionType | None = None
    amount: MoneySchema | None = None
    counter_account_id: uuid.UUID | None = None
    # Metadata-only fields.
    occurred_at: dt.datetime | None = None
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    counterparty: str | None = Field(default=None, max_length=200)
    note: str | None = Field(default=None, max_length=1000)
    status: TransactionStatus | None = None


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    counter_account_id: uuid.UUID | None
    type: TransactionType
    status: TransactionStatus
    amount: MoneySchema
    occurred_at: dt.datetime
    category_id: uuid.UUID | None
    merchant_id: uuid.UUID | None
    counterparty: str | None
    note: str | None
    source: TransactionSource
    categorization_source: CategorizationSource
    external_ref: str | None
    related_transaction_id: uuid.UUID | None
    version: int
    server_seq: int
    created_at: dt.datetime
    updated_at: dt.datetime

    @classmethod
    def from_model(cls, txn: Transaction) -> TransactionOut:
        return cls(
            id=txn.id,
            account_id=txn.account_id,
            counter_account_id=txn.counter_account_id,
            type=txn.type,
            status=txn.status,
            amount=MoneySchema(amount_minor=txn.amount_minor, currency=txn.currency),
            occurred_at=txn.occurred_at,
            category_id=txn.category_id,
            merchant_id=txn.merchant_id,
            counterparty=txn.counterparty,
            note=txn.note,
            source=txn.source,
            categorization_source=txn.categorization_source,
            external_ref=txn.external_ref,
            related_transaction_id=txn.related_transaction_id,
            version=txn.version,
            server_seq=txn.server_seq,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        )
