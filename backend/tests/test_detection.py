"""Tests for recurring-pattern detection."""

from __future__ import annotations

import datetime as dt

from app.domain.detection import RecurringObservation, detect_patterns
from app.domain.enums import RecurrenceInterval

UTC = dt.UTC


def _obs(key: str, amount: int, y: int, m: int, d: int) -> RecurringObservation:
    return RecurringObservation(
        key=key, amount_minor=amount, occurred_at=dt.datetime(y, m, d, 9, tzinfo=UTC)
    )


def test_detects_monthly_subscription() -> None:
    obs = [_obs("Netflix", 64900, 2026, mth, 5) for mth in (1, 2, 3, 4)]
    patterns = detect_patterns(obs, currency="INR")
    assert len(patterns) == 1
    p = patterns[0]
    assert p.key == "Netflix"
    assert p.interval is RecurrenceInterval.MONTHLY
    assert p.occurrences == 4
    assert p.confidence >= 50
    assert p.expected_next == dt.datetime(2026, 5, 5, 9, tzinfo=UTC)


def test_insufficient_occurrences_not_detected() -> None:
    obs = [_obs("Spotify", 11900, 2026, 1, 5), _obs("Spotify", 11900, 2026, 2, 5)]
    assert detect_patterns(obs, currency="INR") == []


def test_irregular_gaps_filtered() -> None:
    obs = [
        _obs("Corner Store", 20000, 2026, 1, 5),
        _obs("Corner Store", 20000, 2026, 1, 10),
        _obs("Corner Store", 20000, 2026, 3, 11),
        _obs("Corner Store", 20000, 2026, 3, 21),
    ]
    # Median gap ~ a handful of days, matching no cadence band -> not recurring.
    assert detect_patterns(obs, currency="INR") == []


def test_different_amounts_are_separate_groups() -> None:
    obs = [
        _obs("Swiggy", 30000, 2026, 1, 5),
        _obs("Swiggy", 30000, 2026, 2, 5),
        _obs("Swiggy", 45000, 2026, 1, 20),
    ]
    # Only the ₹300 group has enough regular occurrences; and it has just 2 -> none.
    assert detect_patterns(obs, currency="INR") == []


def test_weekly_detection() -> None:
    obs = [_obs("Gym", 50000, 2026, 1, day) for day in (5, 12, 19, 26)]
    patterns = detect_patterns(obs, currency="INR")
    assert patterns[0].interval is RecurrenceInterval.WEEKLY
