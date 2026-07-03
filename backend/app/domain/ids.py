"""Identifier generation.

Primary keys are UUIDv7 (RFC 9562): a 48-bit millisecond timestamp followed by
random bits. They are client-generatable (so records can be created offline), globally
unique, and time-sortable (so they index well and preserve insertion order roughly).

Implemented here rather than relying on the stdlib so behaviour is identical across
Python versions and fully deterministic under test (the clock is injectable).
"""

from __future__ import annotations

import os
import time
import uuid


def uuid7(*, ms: int | None = None, rand: bytes | None = None) -> uuid.UUID:
    """Generate a UUIDv7.

    `ms` and `rand` are injectable for deterministic tests; in normal use the current
    wall-clock millisecond and 10 random bytes are used.
    """
    if ms is None:
        ms = time.time_ns() // 1_000_000
    if rand is None:
        rand = os.urandom(10)
    if len(rand) < 10:
        raise ValueError("rand must be at least 10 bytes")

    ts = ms & ((1 << 48) - 1)
    rand_a = int.from_bytes(rand[0:2], "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(rand[2:10], "big") & ((1 << 62) - 1)  # 62 bits

    value = (
        (ts << 80)  # 48-bit timestamp
        | (0x7 << 76)  # 4-bit version
        | (rand_a << 64)  # 12 random bits
        | (0b10 << 62)  # 2-bit variant
        | rand_b  # 62 random bits
    )
    return uuid.UUID(int=value)


def new_id() -> uuid.UUID:
    """Convenience alias for a fresh UUIDv7."""
    return uuid7()
