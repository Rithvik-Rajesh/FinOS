"""Shared FastAPI dependencies (auth, etc.)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header

from app.core.security import Principal, verify_access_token


async def get_current_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    """Resolve the authenticated user from the Authorization header.

    Every data endpoint depends on this; downstream repositories then scope all
    queries to `principal.user_id` (see SECURITY.md#authorization).
    """
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    return await verify_access_token(token)


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]
