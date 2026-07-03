"""The posting engine — the deterministic heart of the transaction system.

Every transaction is projected into one or more **postings** (immutable ledger
entries). Account balances are defined as the sum of their postings, and nothing else.
This is the single source of financial truth.

Sign convention (uniform across account types):

    positive amount  -> the account's balance increases (inflow)
    negative amount  -> the account's balance decreases (outflow)

A credit card is simply an account whose balance is normally negative (money owed);
a purchase posts a negative amount to it, a payment posts a positive amount. No
special-casing per account type is required, which keeps the engine tiny and correct.

Posting rules by transaction type:

    EXPENSE     [ (account, -amount) ]                       single-sided outflow
    INCOME      [ (account, +amount) ]                       single-sided inflow
    REFUND      [ (account, +amount) ]                       single-sided inflow
    ADJUSTMENT  [ (account, ±amount) ]                       signed correction
    TRANSFER    [ (account, -amount), (counter, +amount) ]   balanced, nets to zero

Immutability & history: postings are never mutated or deleted. To edit or delete a
transaction, the service posts the *reversal* of its previous postings and (for edits)
the postings of the new state. Because reversals net out, balances stay exact and the
full financial history is preserved (see TRANSACTION_ENGINE.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.enums import EntryDirection, TransactionType
from app.domain.money import Money, sum_money


class PostingError(ValueError):
    """Raised when a transaction cannot be turned into valid postings."""


@dataclass(frozen=True, slots=True)
class Posting:
    """An immutable movement of money against a single account.

    `amount` is signed: positive increases the account balance, negative decreases it.
    """

    account_id: uuid.UUID
    amount: Money

    @property
    def direction(self) -> EntryDirection:
        return EntryDirection.OUTFLOW if self.amount.is_negative else EntryDirection.INFLOW


@dataclass(frozen=True, slots=True)
class TransactionInput:
    """The minimal, pure view of a transaction needed to compute its postings."""

    type: TransactionType
    amount: Money
    account_id: uuid.UUID
    counter_account_id: uuid.UUID | None = None


def _negate(amount: Money) -> Money:
    return Money(-amount.amount_minor, amount.currency)


def build_postings(txn: TransactionInput) -> list[Posting]:
    """Project a transaction into its balanced set of postings.

    Raises `PostingError` for invalid inputs (non-positive amounts where a magnitude is
    required, missing/aliased counter accounts for transfers, etc.).
    """
    amount = txn.amount

    if txn.type is TransactionType.ADJUSTMENT:
        # Adjustments carry a signed amount (a correction may be up or down) but must
        # not be a no-op.
        if amount.is_zero:
            raise PostingError("adjustment amount must be non-zero")
        return [Posting(txn.account_id, amount)]

    # All non-adjustment types use a positive magnitude.
    if amount.is_negative or amount.is_zero:
        raise PostingError(f"{txn.type} amount must be positive")

    if txn.type in (TransactionType.EXPENSE,):
        return [Posting(txn.account_id, _negate(amount))]

    if txn.type in (TransactionType.INCOME, TransactionType.REFUND):
        return [Posting(txn.account_id, amount)]

    if txn.type is TransactionType.TRANSFER:
        if txn.counter_account_id is None:
            raise PostingError("transfer requires a counter account")
        if txn.counter_account_id == txn.account_id:
            raise PostingError("transfer source and destination must differ")
        return [
            Posting(txn.account_id, _negate(amount)),
            Posting(txn.counter_account_id, amount),
        ]

    raise PostingError(f"unsupported transaction type: {txn.type}")  # pragma: no cover


def reverse_postings(postings: Iterable[Posting]) -> list[Posting]:
    """Return postings that exactly cancel the given ones (for edits and deletes)."""
    return [Posting(p.account_id, _negate(p.amount)) for p in postings]


def nets_to_zero(postings: Iterable[Posting]) -> bool:
    """True when postings balance to zero across accounts (the double-entry invariant).

    Holds for transfers and for any reversal; single-sided income/expense do not net to
    zero because their counterparty is outside the tracked set of accounts.
    """
    postings = list(postings)
    if not postings:
        return True
    currency = postings[0].amount.currency
    return sum_money([p.amount for p in postings], currency).is_zero


def balance_from_postings(postings: Iterable[Posting], currency: str) -> Money:
    """Compute an account balance as the signed sum of its postings."""
    return sum_money([p.amount for p in postings], currency)
