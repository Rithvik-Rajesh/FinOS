"""Tests for the posting engine — the financial source of truth."""

from __future__ import annotations

import uuid

import pytest

from app.domain.enums import EntryDirection, TransactionType
from app.domain.ledger import (
    Posting,
    PostingError,
    TransactionInput,
    balance_from_postings,
    build_postings,
    nets_to_zero,
    reverse_postings,
)
from app.domain.money import Money

ACC = uuid.uuid4()
ACC2 = uuid.uuid4()


def _money(minor: int) -> Money:
    return Money(minor, "INR")


def test_expense_is_single_sided_outflow() -> None:
    postings = build_postings(TransactionInput(TransactionType.EXPENSE, _money(28000), ACC))
    assert postings == [Posting(ACC, _money(-28000))]
    assert postings[0].direction is EntryDirection.OUTFLOW


def test_income_is_single_sided_inflow() -> None:
    postings = build_postings(TransactionInput(TransactionType.INCOME, _money(50000), ACC))
    assert postings == [Posting(ACC, _money(50000))]
    assert postings[0].direction is EntryDirection.INFLOW


def test_refund_returns_money() -> None:
    postings = build_postings(TransactionInput(TransactionType.REFUND, _money(1500), ACC))
    assert postings == [Posting(ACC, _money(1500))]


def test_transfer_is_balanced() -> None:
    postings = build_postings(TransactionInput(TransactionType.TRANSFER, _money(10000), ACC, ACC2))
    assert postings == [Posting(ACC, _money(-10000)), Posting(ACC2, _money(10000))]
    assert nets_to_zero(postings)


def test_adjustment_accepts_signed_amount() -> None:
    up = build_postings(TransactionInput(TransactionType.ADJUSTMENT, _money(500), ACC))
    down = build_postings(TransactionInput(TransactionType.ADJUSTMENT, _money(-500), ACC))
    assert up == [Posting(ACC, _money(500))]
    assert down == [Posting(ACC, _money(-500))]


def test_expense_does_not_net_to_zero() -> None:
    postings = build_postings(TransactionInput(TransactionType.EXPENSE, _money(100), ACC))
    assert not nets_to_zero(postings)


def test_reversal_cancels_original() -> None:
    postings = build_postings(TransactionInput(TransactionType.TRANSFER, _money(7000), ACC, ACC2))
    combined = postings + reverse_postings(postings)
    assert balance_from_postings([p for p in combined if p.account_id == ACC], "INR") == _money(0)
    assert balance_from_postings([p for p in combined if p.account_id == ACC2], "INR") == _money(0)


def test_balance_is_sum_of_postings() -> None:
    postings = [
        Posting(ACC, _money(50000)),
        Posting(ACC, _money(-28000)),
        Posting(ACC, _money(-2000)),
    ]
    assert balance_from_postings(postings, "INR") == _money(20000)


def test_negative_expense_rejected() -> None:
    with pytest.raises(PostingError):
        build_postings(TransactionInput(TransactionType.EXPENSE, _money(-1), ACC))


def test_zero_expense_rejected() -> None:
    with pytest.raises(PostingError):
        build_postings(TransactionInput(TransactionType.EXPENSE, _money(0), ACC))


def test_zero_adjustment_rejected() -> None:
    with pytest.raises(PostingError):
        build_postings(TransactionInput(TransactionType.ADJUSTMENT, _money(0), ACC))


def test_transfer_requires_counter_account() -> None:
    with pytest.raises(PostingError):
        build_postings(TransactionInput(TransactionType.TRANSFER, _money(100), ACC))


def test_transfer_rejects_same_account() -> None:
    with pytest.raises(PostingError):
        build_postings(TransactionInput(TransactionType.TRANSFER, _money(100), ACC, ACC))
