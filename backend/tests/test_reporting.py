"""Tests for the deterministic reporting calculations."""

from __future__ import annotations

import datetime as dt
import uuid
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.enums import Period, TransactionType
from app.domain.money import Money
from app.domain.reporting import (
    TransactionRecord,
    growth,
    net_cashflow,
    spending_by_category,
    spending_by_merchant,
    total_income,
    total_spending,
    totals_by_period,
)

IST = ZoneInfo("Asia/Kolkata")
FOOD = uuid.uuid4()
TRAVEL = uuid.uuid4()
SWIGGY = uuid.uuid4()
UBER = uuid.uuid4()


def _rec(
    minor: int,
    ttype: TransactionType = TransactionType.EXPENSE,
    *,
    when: dt.datetime | None = None,
    category: uuid.UUID | None = None,
    merchant: uuid.UUID | None = None,
) -> TransactionRecord:
    return TransactionRecord(
        id=uuid.uuid4(),
        type=ttype,
        amount=Money(minor, "INR"),
        occurred_at=when or dt.datetime(2026, 7, 3, 12, 0, tzinfo=dt.UTC),
        category_id=category,
        merchant_id=merchant,
    )


def test_total_spending_nets_refunds() -> None:
    records = [
        _rec(30000, TransactionType.EXPENSE),
        _rec(5000, TransactionType.REFUND),
        _rec(100000, TransactionType.INCOME),  # excluded from spend
    ]
    assert total_spending(records, "INR") == Money(25000, "INR")


def test_total_income() -> None:
    records = [_rec(100000, TransactionType.INCOME), _rec(30000, TransactionType.EXPENSE)]
    assert total_income(records, "INR") == Money(100000, "INR")


def test_net_cashflow() -> None:
    records = [_rec(100000, TransactionType.INCOME), _rec(30000, TransactionType.EXPENSE)]
    assert net_cashflow(records, "INR") == Money(70000, "INR")


def test_spending_by_category_sorted_desc() -> None:
    records = [
        _rec(30000, category=FOOD),
        _rec(20000, category=FOOD),
        _rec(80000, category=TRAVEL),
    ]
    groups = spending_by_category(records, "INR")
    assert groups[0].key == TRAVEL
    assert groups[0].total == Money(80000, "INR")
    assert groups[1].key == FOOD
    assert groups[1].total == Money(50000, "INR")
    assert groups[1].count == 2


def test_spending_by_merchant() -> None:
    records = [_rec(28000, merchant=SWIGGY), _rec(12000, merchant=UBER)]
    groups = spending_by_merchant(records, "INR")
    assert groups[0].key == SWIGGY


def test_totals_by_period_month() -> None:
    records = [
        _rec(10000, when=dt.datetime(2026, 6, 15, 6, 0, tzinfo=dt.UTC)),
        _rec(20000, when=dt.datetime(2026, 7, 1, 6, 0, tzinfo=dt.UTC)),
        _rec(5000, when=dt.datetime(2026, 7, 20, 6, 0, tzinfo=dt.UTC)),
    ]
    totals = totals_by_period(records, "INR", Period.MONTH, IST)
    assert [t.period_start for t in totals] == [dt.date(2026, 6, 1), dt.date(2026, 7, 1)]
    assert totals[1].total == Money(25000, "INR")


def test_totals_by_period_respects_timezone() -> None:
    # 2026-07-01 20:00 UTC is 2026-07-02 01:30 IST -> lands in the July-2 local day.
    rec = _rec(10000, when=dt.datetime(2026, 7, 1, 20, 0, tzinfo=dt.UTC))
    totals = totals_by_period([rec], "INR", Period.DAY, IST)
    assert totals[0].period_start == dt.date(2026, 7, 2)


def test_growth_percentage() -> None:
    result = growth(Money(5900, "INR"), Money(5000, "INR"))
    assert result.delta == Money(900, "INR")
    assert result.pct_change == Decimal("18.0")
    assert result.is_new is False


def test_growth_zero_base_is_new() -> None:
    result = growth(Money(5000, "INR"), Money(0, "INR"))
    assert result.pct_change is None
    assert result.is_new is True
