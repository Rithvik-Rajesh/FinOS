"""Opaque keyset (cursor) pagination helpers.

Keyset pagination is used for the transaction ledger because it stays correct and fast
as data grows and as rows are inserted (unlike offset pagination). A cursor encodes the
sort key and id of the last row returned.
"""

from __future__ import annotations

import base64
import binascii
import json
from typing import Any

from app.core.errors import AppError


class InvalidCursorError(AppError):
    status_code = 400
    code = "invalid_cursor"


def encode_cursor(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> dict[str, Any]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode())
        data = json.loads(raw)
    except (binascii.Error, ValueError) as exc:
        raise InvalidCursorError("cursor is malformed") from exc
    if not isinstance(data, dict):
        raise InvalidCursorError("cursor is malformed")
    return data
