"""Sync REST API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.modules.sync import service
from app.modules.sync.schemas import SyncPullResponse, SyncPushRequest, SyncPushResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("", response_model=SyncPullResponse)
async def pull(
    session: DbSession,
    user_id: CurrentUserId,
    since: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> SyncPullResponse:
    """Delta pull. `since=0` is a full-sync recovery; `since>0` is incremental."""
    return await service.pull(session, user_id, since=since, limit=limit)


@router.post("", response_model=SyncPushResponse)
async def push(
    body: SyncPushRequest,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> SyncPushResponse:
    """Push client mutations; returns per-mutation results (applied/conflict/error)."""
    return await service.push(
        session,
        user_id,
        mutations=body.mutations,
        clock=clock,
        correlation_id=correlation_id,
    )
