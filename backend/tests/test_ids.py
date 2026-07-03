"""Tests for UUIDv7 generation."""

from __future__ import annotations

from app.domain.ids import uuid7


def test_uuid7_version_and_variant() -> None:
    u = uuid7()
    assert u.version == 7
    # RFC 9562 variant bits are 0b10.
    assert (u.int >> 62) & 0b11 == 0b10


def test_uuid7_encodes_timestamp() -> None:
    u = uuid7(ms=0x0123456789AB, rand=b"\x00" * 10)
    assert (u.int >> 80) == 0x0123456789AB


def test_uuid7_is_time_sortable() -> None:
    earlier = uuid7(ms=1000, rand=b"\x00" * 10)
    later = uuid7(ms=2000, rand=b"\x00" * 10)
    assert earlier < later


def test_uuid7_unique() -> None:
    assert len({uuid7() for _ in range(1000)}) == 1000


def test_uuid7_rejects_short_rand() -> None:
    try:
        uuid7(rand=b"\x00")
    except ValueError:
        return
    raise AssertionError("expected ValueError")
