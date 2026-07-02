"""Authentication primitives.

FinOS uses Supabase Auth as the identity provider (ADR-003). This module verifies the
access JWT against Supabase's JWKS and returns the authenticated principal. Data access
authorization (tenant scoping) is enforced separately in the repository layer.

For local development without a Supabase project, `auth_dev_bypass` returns a fixed
dev user so the app is runnable end-to-end. This MUST be false in production.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import get_settings
from app.core.errors import UnauthenticatedError

# A stable, obviously-fake UUID for the local dev user.
DEV_USER_ID = "00000000-0000-7000-8000-000000000001"


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated user extracted from a verified JWT."""

    user_id: str
    email: str | None = None
    is_dev: bool = False


def _dev_principal() -> Principal:
    return Principal(user_id=DEV_USER_ID, email="dev@finos.local", is_dev=True)


async def verify_access_token(token: str | None) -> Principal:
    """Verify a bearer token and return the Principal, or raise UnauthenticatedError.

    NOTE: JWKS verification is stubbed pending Supabase wiring (Phase 0 spike). The
    interface is final; only the verification body changes. When dev bypass is on and
    no token is supplied, a fixed dev user is returned.
    """
    settings = get_settings()

    if settings.auth_dev_bypass and not settings.is_prod:
        return _dev_principal()

    if not token:
        raise UnauthenticatedError("Missing bearer token.")

    # TODO(phase-0): fetch+cache JWKS from settings.supabase_jwks_url, verify signature,
    # check exp/aud/iss, extract `sub` as user_id. Uses pyjwt[crypto] + httpx.
    raise UnauthenticatedError("JWT verification not yet configured.")
