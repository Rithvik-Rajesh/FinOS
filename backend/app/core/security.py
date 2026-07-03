"""Authentication primitives.

FinOS uses Supabase Auth as the identity provider (ADR-003, ADR-012). This module verifies
the access JWT against Supabase's JWKS (asymmetric RS256/ES256) and returns the
authenticated principal. Tenant scoping is enforced separately in the repository layer.

Security decisions (see SECURITY.md):
* Signature is verified against the provider's published JWKS — the API never holds a
  shared secret, and key rotation is handled by refetching the JWKS.
* `exp` and `sub` are required; `aud` is checked against the configured audience.
* JWKS fetching is synchronous inside pyjwt, so it runs in a worker thread to avoid
  blocking the event loop; pyjwt caches keys between calls.
* `auth_dev_bypass` returns a fixed dev user for local development and tests; it is
  ignored in production (`env=prod`), where a missing/invalid token always 401s.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.errors import UnauthenticatedError

# A stable, obviously-fake UUID for the local dev user.
DEV_USER_ID = "00000000-0000-7000-8000-000000000001"
_ALGORITHMS = ["RS256", "ES256"]


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated user extracted from a verified JWT."""

    user_id: str
    email: str | None = None
    is_dev: bool = False


def _dev_principal() -> Principal:
    return Principal(user_id=DEV_USER_ID, email="dev@finos.local", is_dev=True)


@lru_cache
def _jwk_client() -> PyJWKClient:
    """Cached JWKS client (pyjwt caches signing keys and refetches on rotation)."""
    return PyJWKClient(get_settings().supabase_jwks_url)


def _decode(token: str) -> dict[str, Any]:
    settings = get_settings()
    signing_key = _jwk_client().get_signing_key_from_jwt(token)
    claims: dict[str, Any] = jwt.decode(
        token,
        signing_key.key,
        algorithms=_ALGORITHMS,
        audience=settings.jwt_audience,
        options={"require": ["exp", "sub"]},
    )
    return claims


async def verify_access_token(token: str | None) -> Principal:
    """Verify a bearer token and return the Principal, or raise UnauthenticatedError."""
    settings = get_settings()

    if settings.auth_dev_bypass and not settings.is_prod:
        return _dev_principal()

    if not token:
        raise UnauthenticatedError("Missing bearer token.")

    try:
        claims = await asyncio.to_thread(_decode, token)
    except Exception as exc:  # noqa: BLE001 - all verification failures map to 401
        raise UnauthenticatedError("Invalid or expired token.") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise UnauthenticatedError("Token is missing a subject.")
    email = claims.get("email")
    return Principal(user_id=subject, email=email if isinstance(email, str) else None)
