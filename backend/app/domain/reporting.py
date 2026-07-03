"""Deterministic reporting calculations.

Pure aggregation over transaction records — no database, no AI, no floats for money.
These functions are the canonical definitions of every headline number in the app
(spending by category/merchant, period totals, growth). Future AI features *consume*
these outputs; they never recompute them (see REPORTING_ENGINE.md).

Spending convention: EXPENSE increases spending, REFUND decreases it (net spend).
TRANSFER and ADJUSTMENT are excluded from spending and income; INCOME feeds income
totals only. Reports operate on a single currency and reject mixed-currency inputs.
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import Period, TransactionType
from app.domain.money import CurrencyMismatchError, Money


@dataclass(frozen=True, slots=True)
class TransactionRecord:
    """A lightweight, pure view of a transaction for reporting.

    `amount` is always a positive magnitude; direction is implied by `type`.
    """

    id: uuid.UUID
    type: TransactionType
    amount: Money
    occurred_at: dt.datetime
    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class GroupTotal:
    """A total for one grouping key (category or merchant)."""

    key: uuid.UUID | None
    total: Money
    count: int


@dataclass(frozen=True, slots=True)
class PeriodTotal:
    period: Period
    period_start: dt.date
    total: Money
    count: int


@dataclass(frozen=True, slots=True)
class GrowthResult:
    """Change between two comparable amounts."""

    current: Money
    previous: Money
    delta: Money
    pct_change: Decimal | None  # None when there is no prior base to compare against
    is_new: bool  # True when previous is zero but current is not


def _require_currency(records: Sequence[TransactionRecord], currency: str) -> None:
    for record in records:
        if record.amount.currency != currency:
            raise CurrencyMismatchError(
                f"report currency {currency} but record is {record.amount.currency}"
            )


def _signed_spend(record: TransactionRecord) -> int:
    """Contribution of a record to *net spending*, in minor units."""
    if record.type is TransactionType.EXPENSE:
        return record.amount.amount_minor
    if record.type is TransactionType.REFUND:
        return -record.amount.amount_minor
    return 0


def total_spending(records: Sequence[TransactionRecord], currency: str) -> Money:
    _require_currency(records, currency)
    return Money(sum(_signed_spend(r) for r in records), currency)


def total_income(records: Sequence[TransactionRecord], currency: str) -> Money:
    _require_currency(records, currency)
    total = sum(r.amount.amount_minor for r in records if r.type is TransactionType.INCOME)
    return Money(total, currency)


def net_cashflow(records: Sequence[TransactionRecord], currency: str) -> Money:
    """Income minus net spending."""
    return total_income(records, currency) - total_spending(records, currency)


def _group_by(
    records: Sequence[TransactionRecord],
    currency: str,
    key: str,
) -> list[GroupTotal]:
    _require_currency(records, currency)
    totals: dict[uuid.UUID | None, int] = {}
    counts: dict[uuid.UUID | None, int] = {}
    for record in records:
        spend = _signed_spend(record)
        if spend == 0:
            continue
        group_key: uuid.UUID | None = getattr(record, key)
        totals[group_key] = totals.get(group_key, 0) + spend
        counts[group_key] = counts.get(group_key, 0) + 1

    groups = [
        GroupTotal(key=k, total=Money(v, currency), count=counts[k]) for k, v in totals.items()
    ]
    # Deterministic order: largest spend first, then by key for stable ties.
    groups.sort(key=lambda g: (-g.total.amount_minor, str(g.key)))
    return groups


def spending_by_category(records: Sequence[TransactionRecord], currency: str) -> list[GroupTotal]:
    return _group_by(records, currency, "category_id")


def spending_by_merchant(records: Sequence[TransactionRecord], currency: str) -> list[GroupTotal]:
    return _group_by(records, currency, "merchant_id")


def _period_start(moment: dt.datetime, period: Period, tz: dt.tzinfo) -> dt.date:
    local = moment.astimezone(tz).date()
    match period:
        case Period.DAY:
            return local
        case Period.WEEK:
            return local - dt.timedelta(days=local.weekday())  # Monday
        case Period.MONTH:
            return local.replace(day=1)
        case Period.YEAR:
            return local.replace(month=1, day=1)


def totals_by_period(
    records: Sequence[TransactionRecord],
    currency: str,
    period: Period,
    tz: dt.tzinfo,
) -> list[PeriodTotal]:
    """Net-spending totals bucketed by local calendar period, oldest first."""
    _require_currency(records, currency)
    totals: dict[dt.date, int] = {}
    counts: dict[dt.date, int] = {}
    for record in records:
        spend = _signed_spend(record)
        if spend == 0:
            continue
        start = _period_start(record.occurred_at, period, tz)
        totals[start] = totals.get(start, 0) + spend
        counts[start] = counts.get(start, 0) + 1

    result = [
        PeriodTotal(
            period=period, period_start=start, total=Money(v, currency), count=counts[start]
        )
        for start, v in totals.items()
    ]
    result.sort(key=lambda p: p.period_start)
    return result


def growth(current: Money, previous: Money) -> GrowthResult:
    """Compute the change from `previous` to `current`.

    `pct_change` is a Decimal rounded to one place, or None when there is no prior base
    (previous is zero). `is_new` flags a zero-to-nonzero jump.
    """
    delta = current - previous  # raises on currency mismatch
    if previous.is_zero:
        return GrowthResult(
            current=current,
            previous=previous,
            delta=delta,
            pct_change=None,
            is_new=not current.is_zero,
        )
    pct = (Decimal(delta.amount_minor) / Decimal(previous.amount_minor) * Decimal(100)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    return GrowthResult(
        current=current, previous=previous, delta=delta, pct_change=pct, is_new=False
    )
