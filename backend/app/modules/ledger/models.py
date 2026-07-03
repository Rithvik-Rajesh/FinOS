"""Transaction and ledger-entry ORM models.

`Transaction` is the user-facing record. `LedgerEntry` rows are the immutable postings
that define account balances (see app.domain.ledger and TRANSACTION_ENGINE.md). Entries
are append-only: edits and deletes append reversing entries, never mutate existing ones.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SyncMixin, utcnow
from app.domain.enums import (
    CategorizationSource,
    TransactionSource,
    TransactionStatus,
    TransactionType,
)
from app.domain.ids import new_id


class Transaction(Base, SyncMixin):
    __tablename__ = "transactions"

    # Composite indexes matching the real query patterns (docs/DATABASE.md#indexing).
    __table_args__ = (
        Index("ix_txn_user_seq", "user_id", "server_seq"),  # sync delta pull
        Index("ix_txn_user_occurred", "user_id", "occurred_at"),  # ledger list / date range
        Index("ix_txn_user_account_occurred", "user_id", "account_id", "occurred_at"),
        Index("ix_txn_user_category_occurred", "user_id", "category_id", "occurred_at"),
        Index("ix_txn_user_merchant_occurred", "user_id", "merchant_id", "occurred_at"),
        # Idempotent ingestion: at most one row per (user, source, external_ref).
        Index("ix_txn_user_source_extref", "user_id", "source", "external_ref", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column()
    account_id: Mapped[uuid.UUID] = mapped_column()
    counter_account_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    type: Mapped[TransactionType] = mapped_column(Enum(TransactionType, native_enum=False))
    status: Mapped[TransactionStatus] = mapped_column(
        Enum(TransactionStatus, native_enum=False), default=TransactionStatus.CLEARED
    )
    # Positive magnitude for all types except ADJUSTMENT, which may be signed.
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    occurred_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    category_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    merchant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    note: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source: Mapped[TransactionSource] = mapped_column(
        Enum(TransactionSource, native_enum=False), default=TransactionSource.MANUAL
    )
    categorization_source: Mapped[CategorizationSource] = mapped_column(
        Enum(CategorizationSource, native_enum=False), default=CategorizationSource.MANUAL
    )
    # Idempotent ingestion key (unique per user+source); links refunds to originals.
    external_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class LedgerEntry(Base):
    """An immutable posting against one account. Never updated or deleted."""

    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    user_id: Mapped[uuid.UUID] = mapped_column(index=True)
    transaction_id: Mapped[uuid.UUID] = mapped_column(index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Signed: positive increases the account balance, negative decreases it.
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    # The transaction version this entry was posted for (audit of the entry stream).
    txn_version: Mapped[int] = mapped_column(Integer)
    is_reversal: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
