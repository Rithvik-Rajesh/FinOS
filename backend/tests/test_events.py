"""Tests for domain event definitions."""

from __future__ import annotations

import datetime as dt
import uuid

from app.domain.enums import CategorizationSource, TransactionType
from app.domain.events import (
    AccountCreated,
    RuleApplied,
    TransactionCreated,
)

USER = uuid.uuid4()
NOW = dt.datetime(2026, 7, 3, 12, 0, tzinfo=dt.UTC)


def test_event_name() -> None:
    event = AccountCreated(
        user_id=USER, occurred_at=NOW, account_id=uuid.uuid4(), type="cash", currency="INR"
    )
    assert event.name == "AccountCreated"


def test_payload_is_jsonable() -> None:
    txn_id = uuid.uuid4()
    event = TransactionCreated(
        user_id=USER,
        occurred_at=NOW,
        transaction_id=txn_id,
        type=TransactionType.EXPENSE,
        amount_minor=28000,
        currency="INR",
        account_id=uuid.uuid4(),
    )
    payload = event.to_payload()
    assert payload["transaction_id"] == str(txn_id)
    assert payload["type"] == "expense"
    assert payload["occurred_at"] == NOW.isoformat()
    assert payload["user_id"] == str(USER)


def test_rule_applied_serializes_tuple_and_enum() -> None:
    ids = (uuid.uuid4(), uuid.uuid4())
    event = RuleApplied(
        user_id=USER,
        occurred_at=NOW,
        transaction_id=uuid.uuid4(),
        rule_ids=ids,
        category_id=None,
        source=CategorizationSource.USER_RULE,
    )
    payload = event.to_payload()
    assert payload["rule_ids"] == [str(ids[0]), str(ids[1])]
    assert payload["source"] == "user_rule"
    assert payload["category_id"] is None


def test_events_are_frozen() -> None:
    event = AccountCreated(
        user_id=USER, occurred_at=NOW, account_id=uuid.uuid4(), type="cash", currency="INR"
    )
    try:
        event.type = "savings"  # type: ignore[misc]
    except AttributeError:
        return
    raise AssertionError("event should be immutable")
