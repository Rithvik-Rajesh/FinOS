"""Unit tests for review math and auth."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.money import CurrencyMismatchError, Money
from app.domain.reviews import savings_rate


def _m(rupees: int) -> Money:
    return Money(rupees * 100, "INR")


def test_savings_rate_positive() -> None:
    assert savings_rate(income=_m(100000), spending=_m(60000)) == Decimal("40.0")


def test_savings_rate_negative_when_overspending() -> None:
    assert savings_rate(income=_m(50000), spending=_m(60000)) == Decimal("-20.0")


def test_savings_rate_none_without_income() -> None:
    assert savings_rate(income=_m(0), spending=_m(1000)) is None


def test_savings_rate_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        savings_rate(income=Money(100, "INR"), spending=Money(50, "USD"))
