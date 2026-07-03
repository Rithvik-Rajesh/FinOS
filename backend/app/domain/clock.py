"""Time as an injectable dependency.

The domain never reads the wall clock implicitly — any function that needs "now"
receives a `Clock`. This keeps the domain deterministic and testable (`FixedClock`),
while production wires a `SystemClock`.
"""

from __future__ import annotations

import datetime as dt
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    def now(self) -> dt.datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Reads the real clock. Used in production."""

    def now(self) -> dt.datetime:
        return dt.datetime.now(dt.UTC)


class FixedClock:
    """A clock frozen at a given instant. Used in tests and simulations."""

    def __init__(self, instant: dt.datetime) -> None:
        if instant.tzinfo is None:
            raise ValueError("FixedClock requires a timezone-aware datetime")
        self._instant = instant

    def now(self) -> dt.datetime:
        return self._instant
