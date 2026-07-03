"""Notifications REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi import status as http_status

from app.api.deps import ClockDep, CurrentUserId, DbSession
from app.api.schemas import Page
from app.domain.enums import NotificationStatus, NotificationType
from app.modules.notifications import repository as repo
from app.modules.notifications import service
from app.modules.notifications.schemas import (
    NotificationEventOut,
    NotificationRuleOut,
    NotificationRuleUpdate,
    PreferenceOut,
    PreferenceUpdate,
    ScanResponse,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=Page[NotificationEventOut])
async def list_events(
    session: DbSession,
    user_id: CurrentUserId,
    status: NotificationStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[NotificationEventOut]:
    rows = await repo.list_events(session, user_id, status=status, limit=limit, offset=offset)
    return Page(
        items=[NotificationEventOut.model_validate(r) for r in rows], has_more=len(rows) == limit
    )


@router.post("/scan", response_model=ScanResponse)
async def scan(
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    currency: Annotated[str, Query(min_length=3, max_length=3)] = "INR",
) -> ScanResponse:
    created = await service.scan(session, user_id=user_id, currency=currency, clock=clock)
    return ScanResponse(created=created)


@router.get("/rules", response_model=list[NotificationRuleOut])
async def list_rules(session: DbSession, user_id: CurrentUserId) -> list[NotificationRuleOut]:
    rules = await service.ensure_rules(session, user_id)
    return [NotificationRuleOut.model_validate(r) for r in rules]


@router.patch("/rules/{ntype}", response_model=NotificationRuleOut)
async def update_rule(
    ntype: NotificationType,
    body: NotificationRuleUpdate,
    session: DbSession,
    user_id: CurrentUserId,
) -> NotificationRuleOut:
    rule = await service.update_rule(
        session, user_id=user_id, ntype=ntype, changes=body.model_dump(exclude_unset=True)
    )
    return NotificationRuleOut.model_validate(rule)


@router.get("/preferences", response_model=PreferenceOut)
async def get_preferences(session: DbSession, user_id: CurrentUserId) -> PreferenceOut:
    pref = await service.get_or_create_preference(session, user_id)
    return PreferenceOut.model_validate(pref)


@router.patch("/preferences", response_model=PreferenceOut)
async def update_preferences(
    body: PreferenceUpdate, session: DbSession, user_id: CurrentUserId
) -> PreferenceOut:
    pref = await service.update_preference(
        session, user_id=user_id, changes=body.model_dump(exclude_unset=True)
    )
    return PreferenceOut.model_validate(pref)


@router.post("/{event_id}/read", status_code=http_status.HTTP_204_NO_CONTENT)
async def mark_read(
    event_id: uuid.UUID, session: DbSession, user_id: CurrentUserId, clock: ClockDep
) -> None:
    await service.mark(
        session, user_id=user_id, event_id=event_id, status=NotificationStatus.READ, clock=clock
    )


@router.post("/{event_id}/dismiss", status_code=http_status.HTTP_204_NO_CONTENT)
async def mark_dismissed(
    event_id: uuid.UUID, session: DbSession, user_id: CurrentUserId, clock: ClockDep
) -> None:
    await service.mark(
        session,
        user_id=user_id,
        event_id=event_id,
        status=NotificationStatus.DISMISSED,
        clock=clock,
    )
