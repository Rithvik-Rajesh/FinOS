"""Unit tests for the Money value type — the foundation of every financial figure."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.money import CurrencyMismatchError, Money, sum_money


def test_of_converts_major_to_minor_units() -> None:
    assert Money.of("95000.50", "INR").amount_minor == 9500050
    assert Money.of(100, "INR").amount_minor == 10000


def test_of_rejects_float_via_decimal_precision() -> None:
    # Banker's rounding at the currency's exponent, exact via Decimal.
    assert Money.of("1.005", "INR").amount_minor == 100  # rounds half-even to 1.00
    assert Money.of("1.015", "INR").amount_minor == 102  # rounds half-even to 1.02


def test_addition_and_subtraction() -> None:
    a = Money(28000, "INR")
    b = Money(2000, "INR")
    assert (a + b).amount_minor == 30000
    assert (a - b).amount_minor == 26000


def test_scale_is_exact() -> None:
    monthly = Money.of("799", "INR")
    assert monthly.scale(12) == Money.of("9588", "INR")


def test_currency_mismatch_raises() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money(100, "INR") + Money(100, "USD")


def test_amount_minor_must_be_int_not_float() -> None:
    with pytest.raises(TypeError):
        Money(1.5, "INR")  # type: ignore[arg-type]


def test_invalid_currency_rejected() -> None:
    with pytest.raises(ValueError):
        Money(100, "RUPEE")


def test_currency_is_normalized_uppercase() -> None:
    assert Money(100, "inr").currency == "INR"


def test_major_is_exact_decimal() -> None:
    assert Money(9500050, "INR").major == Decimal("95000.50")


def test_sum_money() -> None:
    items = [Money(100, "INR"), Money(250, "INR"), Money(50, "INR")]
    assert sum_money(items, "INR") == Money(400, "INR")


def test_predicates() -> None:
    assert Money.zero("INR").is_zero
    assert Money(-1, "INR").is_negative
    assert Money(100, "INR") > Money(50, "INR")
