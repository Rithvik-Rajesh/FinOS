"""Recurring-pattern detection — deterministic, explainable, no ML.

Given a history of like transactions (same payee + amount), find a regular cadence and
score how confident we are. The output feeds a *user-approval* workflow — detection never
creates obligations on its own. Designed so future SMS/bank-ingested observations feed the
exact same detector (see RECURRING_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
import statistics
from collections import defaultdict
from dataclasses import dataclass

from app.domain.enums import RecurrenceInterval
from app.domain.recurrence import RecurrenceSpec, next_occurrence

# (interval, inclusive day-gap tolerance) ordered from shortest to longest cadence.
_INTERVAL_BANDS: list[tuple[RecurrenceInterval, int, int]] = [
    (RecurrenceInterval.DAILY, 1, 1),
    (RecurrenceInterval.WEEKLY, 6, 8),
    (RecurrenceInterval.MONTHLY, 27, 32),
    (RecurrenceInterval.QUARTERLY, 85, 95),
    (RecurrenceInterval.YEARLY, 358, 372),
]
MIN_OCCURRENCES = 3
MIN_CONFIDENCE = 50


@dataclass(frozen=True, slots=True)
class RecurringObservation:
    """One observed transaction for detection."""

    key: str  # stable grouping key (e.g. merchant name/id)
    amount_minor: int
    occurred_at: dt.datetime


@dataclass(frozen=True, slots=True)
class DetectedPattern:
    key: str
    amount_minor: int
    currency: str
    interval: RecurrenceInterval
    occurrences: int
    confidence: int  # 0–100
    first_seen: dt.datetime
    last_seen: dt.datetime
    expected_next: dt.datetime


def _classify(gap: float) -> RecurrenceInterval | None:
    for interval, low, high in _INTERVAL_BANDS:
        if low <= gap <= high:
            return interval
    return None


def _regularity(gaps: list[int], interval: RecurrenceInterval) -> float:
    low, high = next((lo, hi) for iv, lo, hi in _INTERVAL_BANDS if iv is interval)
    within = sum(1 for g in gaps if low <= g <= high)
    return within / len(gaps)


def detect_patterns(
    observations: list[RecurringObservation],
    *,
    currency: str,
    min_occurrences: int = MIN_OCCURRENCES,
    min_confidence: int = MIN_CONFIDENCE,
) -> list[DetectedPattern]:
    """Detect recurring series from observations, most confident first.

    Groups by (key, exact amount): a subscription's amount is stable, and grouping on it
    keeps a variable-amount merchant (e.g. groceries) from being flagged as recurring.
    """
    groups: dict[tuple[str, int], list[dt.datetime]] = defaultdict(list)
    for obs in observations:
        groups[(obs.key, obs.amount_minor)].append(obs.occurred_at)

    patterns: list[DetectedPattern] = []
    for (key, amount_minor), dates in groups.items():
        if len(dates) < min_occurrences:
            continue
        dates.sort()
        gaps = [(b - a).days for a, b in zip(dates, dates[1:], strict=False)]
        if not gaps:
            continue
        interval = _classify(statistics.median(gaps))
        if interval is None:
            continue
        regularity = _regularity(gaps, interval)
        count_factor = min(1.0, len(dates) / 6)
        confidence = round(100 * (0.6 * regularity + 0.4 * count_factor))
        if regularity < 0.5 or confidence < min_confidence:
            continue
        last_seen = dates[-1]
        patterns.append(
            DetectedPattern(
                key=key,
                amount_minor=amount_minor,
                currency=currency,
                interval=interval,
                occurrences=len(dates),
                confidence=confidence,
                first_seen=dates[0],
                last_seen=last_seen,
                expected_next=next_occurrence(RecurrenceSpec(interval, last_seen), last_seen),
            )
        )

    patterns.sort(key=lambda p: (-p.confidence, p.key))
    return patterns
