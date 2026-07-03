"""Recurrence engine — the single deterministic source of "when does this repeat?".

One abstraction powers recurring expenses, subscriptions, salary, and the financial
calendar (ADR-007, ADR-010). It is interval-based (daily/weekly/monthly/quarterly/yearly)
with month-end clamping — deterministic and pure. Full iCal RRULE (BYDAY, etc.) is a
documented future extension; the interface would not change.
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from app.domain.enums import RecurrenceInterval

_MONTH_STEP = {
    RecurrenceInterval.MONTHLY: 1,
    RecurrenceInterval.QUARTERLY: 3,
    RecurrenceInterval.YEARLY: 12,
}
_MAX_ITER = 10_000  # safety bound on any generation loop


@dataclass(frozen=True, slots=True)
class RecurrenceSpec:
    """A fixed-interval recurrence anchored at a known occurrence.

    `anchor` is a real occurrence (typically the series start / first due date). Its
    time-of-day and day-of-month define subsequent occurrences; month-family intervals
    clamp the day to the target month's length (Jan 31 -> Feb 28/29 -> Mar 31).
    """

    interval: RecurrenceInterval
    anchor: dt.datetime

    def __post_init__(self) -> None:
        if self.anchor.tzinfo is None:
            raise ValueError("RecurrenceSpec.anchor must be timezone-aware")


def occurrence(spec: RecurrenceSpec, k: int) -> dt.datetime:
    """The k-th occurrence (k >= 0) counting from the anchor (k=0 is the anchor)."""
    if k < 0:
        raise ValueError("k must be non-negative")
    anchor = spec.anchor
    if spec.interval is RecurrenceInterval.DAILY:
        return anchor + dt.timedelta(days=k)
    if spec.interval is RecurrenceInterval.WEEKLY:
        return anchor + dt.timedelta(weeks=k)
    months = _MONTH_STEP[spec.interval] * k
    index = anchor.month - 1 + months
    year = anchor.year + index // 12
    month = index % 12 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return anchor.replace(year=year, month=month, day=day)


def _approx_start_index(spec: RecurrenceSpec, start: dt.datetime) -> int:
    """A lower-bound k near `start`, refined by the caller."""
    if start <= spec.anchor:
        return 0
    if spec.interval is RecurrenceInterval.DAILY:
        return (start.date() - spec.anchor.date()).days
    if spec.interval is RecurrenceInterval.WEEKLY:
        return (start.date() - spec.anchor.date()).days // 7
    months = (start.year - spec.anchor.year) * 12 + (start.month - spec.anchor.month)
    return max(0, months // _MONTH_STEP[spec.interval])


def occurrences_between(
    spec: RecurrenceSpec, start: dt.datetime, end: dt.datetime
) -> list[dt.datetime]:
    """All occurrences in the inclusive window [start, end], ascending."""
    if end < start:
        return []
    k = _approx_start_index(spec, start)
    # Walk back to make sure we didn't overshoot the first in-window occurrence.
    while k > 0 and occurrence(spec, k - 1) >= start:
        k -= 1
    result: list[dt.datetime] = []
    for _ in range(_MAX_ITER):
        current = occurrence(spec, k)
        if current > end:
            break
        if current >= start:
            result.append(current)
        k += 1
    return result


def next_occurrence(spec: RecurrenceSpec, after: dt.datetime) -> dt.datetime:
    """The first occurrence strictly after `after`."""
    k = _approx_start_index(spec, after)
    while k > 0 and occurrence(spec, k - 1) > after:
        k -= 1
    for _ in range(_MAX_ITER):
        current = occurrence(spec, k)
        if current > after:
            return current
        k += 1
    raise RuntimeError("next_occurrence exceeded iteration bound")  # pragma: no cover
