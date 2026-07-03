"""Tests for the recurrence engine."""

from __future__ import annotations

import datetime as dt

import pytest

from app.domain.enums import RecurrenceInterval
from app.domain.recurrence import (
    RecurrenceSpec,
    next_occurrence,
    occurrence,
    occurrences_between,
)

UTC = dt.UTC


def _at(y: int, m: int, d: int, h: int = 9) -> dt.datetime:
    return dt.datetime(y, m, d, h, 0, tzinfo=UTC)


def test_monthly_clamps_month_end() -> None:
    spec = RecurrenceSpec(RecurrenceInterval.MONTHLY, _at(2026, 1, 31))
    assert occurrence(spec, 1) == _at(2026, 2, 28)  # Feb clamps
    assert occurrence(spec, 2) == _at(2026, 3, 31)  # restores intent
    assert occurrence(spec, 3) == _at(2026, 4, 30)


def test_monthly_leap_year_clamp() -> None:
    spec = RecurrenceSpec(RecurrenceInterval.MONTHLY, _at(2028, 1, 31))
    assert occurrence(spec, 1) == _at(2028, 2, 29)  # 2028 is a leap year


def test_occurrences_between_window() -> None:
    spec = RecurrenceSpec(RecurrenceInterval.MONTHLY, _at(2026, 1, 15))
    got = occurrences_between(spec, _at(2026, 3, 1), _at(2026, 6, 30))
    assert got == [_at(2026, 3, 15), _at(2026, 4, 15), _at(2026, 5, 15), _at(2026, 6, 15)]


def test_next_occurrence_after() -> None:
    spec = RecurrenceSpec(RecurrenceInterval.MONTHLY, _at(2026, 1, 15))
    assert next_occurrence(spec, _at(2026, 3, 20)) == _at(2026, 4, 15)
    # Exactly on an occurrence returns the *next* one (strictly after).
    assert next_occurrence(spec, _at(2026, 4, 15)) == _at(2026, 5, 15)


def test_weekly_and_daily() -> None:
    weekly = RecurrenceSpec(RecurrenceInterval.WEEKLY, _at(2026, 1, 1))
    assert occurrence(weekly, 3) == _at(2026, 1, 22)
    daily = RecurrenceSpec(RecurrenceInterval.DAILY, _at(2026, 1, 1))
    assert occurrence(daily, 10) == _at(2026, 1, 11)


def test_quarterly_and_yearly() -> None:
    q = RecurrenceSpec(RecurrenceInterval.QUARTERLY, _at(2026, 1, 10))
    assert occurrence(q, 1) == _at(2026, 4, 10)
    y = RecurrenceSpec(RecurrenceInterval.YEARLY, _at(2026, 3, 1))
    assert occurrence(y, 2) == _at(2028, 3, 1)


def test_empty_window_and_reversed() -> None:
    spec = RecurrenceSpec(RecurrenceInterval.MONTHLY, _at(2026, 1, 15))
    assert occurrences_between(spec, _at(2026, 6, 30), _at(2026, 3, 1)) == []


def test_naive_anchor_rejected() -> None:
    with pytest.raises(ValueError):
        RecurrenceSpec(RecurrenceInterval.MONTHLY, dt.datetime(2026, 1, 1))  # noqa: DTZ001
