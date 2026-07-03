"""Domain event definitions — pure, immutable value objects.

Events are how modules stay decoupled: the ledger publishes facts ("a transaction was
created") and other modules subscribe, rather than calling each other directly. The
event *types* live in the domain (no I/O); the *publishing* mechanism (bus + outbox)
lives in `app.events` (see EVENT_ARCHITECTURE.md).
"""

from __future__ import annotations

import datetime as dt
import enum
import uuid
from dataclasses import dataclass, field, fields
from typing import Any

from app.domain.enums import CategorizationSource, TransactionType
from app.domain.ids import new_id


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


@dataclass(frozen=True, kw_only=True, slots=True)
class DomainEvent:
    """Base class for all domain events."""

    user_id: uuid.UUID
    occurred_at: dt.datetime
    event_id: uuid.UUID = field(default_factory=new_id)

    @property
    def name(self) -> str:
        return type(self).__name__

    def to_payload(self) -> dict[str, Any]:
        """A JSON-serializable representation for the transactional outbox."""
        return {f.name: _jsonable(getattr(self, f.name)) for f in fields(self)}


@dataclass(frozen=True, kw_only=True, slots=True)
class TransactionCreated(DomainEvent):
    transaction_id: uuid.UUID
    type: TransactionType
    amount_minor: int
    currency: str
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class TransactionUpdated(DomainEvent):
    transaction_id: uuid.UUID
    version: int
    changed_fields: tuple[str, ...]


@dataclass(frozen=True, kw_only=True, slots=True)
class TransactionDeleted(DomainEvent):
    transaction_id: uuid.UUID


@dataclass(frozen=True, kw_only=True, slots=True)
class RuleApplied(DomainEvent):
    transaction_id: uuid.UUID
    rule_ids: tuple[uuid.UUID, ...]
    category_id: uuid.UUID | None
    source: CategorizationSource


@dataclass(frozen=True, kw_only=True, slots=True)
class AccountCreated(DomainEvent):
    account_id: uuid.UUID
    type: str
    currency: str
