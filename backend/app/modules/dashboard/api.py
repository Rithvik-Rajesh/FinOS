"""Dashboard REST API — a single call powers the home screen."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.modules.dashboard import service
from app.modules.dashboard.schemas import DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> DashboardResponse:
    return await service.build_dashboard(session, user_id=user_id, currency=currency, clock=clock)
