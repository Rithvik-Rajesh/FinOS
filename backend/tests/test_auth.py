"""Authentication tests — dev bypass and production JWKS verification paths."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.core.errors import UnauthenticatedError
from app.core.security import verify_access_token


async def test_dev_bypass_returns_dev_user() -> None:
    principal = await verify_access_token(None)
    assert principal.is_dev is True
    assert principal.user_id


async def test_missing_token_rejected_when_bypass_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINOS_AUTH_DEV_BYPASS", "false")
    monkeypatch.setenv("FINOS_ENV", "staging")
    get_settings.cache_clear()
    try:
        with pytest.raises(UnauthenticatedError):
            await verify_access_token(None)
    finally:
        get_settings.cache_clear()


async def test_invalid_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FINOS_AUTH_DEV_BYPASS", "false")
    monkeypatch.setenv("FINOS_ENV", "staging")
    get_settings.cache_clear()
    try:
        with pytest.raises(UnauthenticatedError):
            await verify_access_token("not-a-real-jwt")
    finally:
        get_settings.cache_clear()
