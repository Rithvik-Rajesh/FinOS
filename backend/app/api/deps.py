"""Shared FastAPI dependencies (auth, db session, clock, request context)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Principal, verify_access_token
from app.db.session import get_session
from app.domain.clock import Clock, SystemClock


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


async def get_user_id(principal: CurrentPrincipal) -> uuid.UUID:
    return uuid.UUID(principal.user_id)


CurrentUserId = Annotated[uuid.UUID, Depends(get_user_id)]

DbSession = Annotated[AsyncSession, Depends(get_session)]


def get_clock() -> Clock:
    return SystemClock()


ClockDep = Annotated[Clock, Depends(get_clock)]


def get_correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None)
    return correlation_id if isinstance(correlation_id, str) else "unknown"


CorrelationId = Annotated[str, Depends(get_correlation_id)]
