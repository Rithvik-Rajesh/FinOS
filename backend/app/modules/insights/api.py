"""Insights REST API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.modules.insights import service
from app.modules.insights.schemas import InsightOut, InsightsResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightsResponse)
async def list_insights(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> InsightsResponse:
    insights = await service.generate(session, user_id=user_id, currency=currency, clock=clock)
    return InsightsResponse(items=[InsightOut.from_domain(i) for i in insights])
