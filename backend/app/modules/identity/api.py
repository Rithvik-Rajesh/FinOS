"""Profile & preferences REST API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUserId, DbSession
from app.modules.identity import service
from app.modules.identity.models import UserProfile
from app.modules.identity.schemas import (
    PreferencesOut,
    PreferencesUpdate,
    ProfileOut,
    ProfileUpdate,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _prefs(profile: UserProfile) -> PreferencesOut:
    return PreferencesOut(
        financial_priority=profile.financial_priority,
        risk_profile=profile.risk_profile,
        monthly_income_minor=profile.monthly_income_minor,
    )


@router.get("", response_model=ProfileOut)
async def get_profile(session: DbSession, user_id: CurrentUserId) -> ProfileOut:
    profile = await service.get_or_create(session, user_id=user_id)
    return ProfileOut.model_validate(profile)


@router.patch("", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdate, session: DbSession, user_id: CurrentUserId
) -> ProfileOut:
    profile = await service.update_profile(session, user_id=user_id, data=body)
    return ProfileOut.model_validate(profile)


@router.get("/preferences", response_model=PreferencesOut)
async def get_preferences(session: DbSession, user_id: CurrentUserId) -> PreferencesOut:
    profile = await service.get_or_create(session, user_id=user_id)
    return _prefs(profile)


@router.patch("/preferences", response_model=PreferencesOut)
async def update_preferences(
    body: PreferencesUpdate, session: DbSession, user_id: CurrentUserId
) -> PreferencesOut:
    profile = await service.update_preferences(session, user_id=user_id, data=body)
    return _prefs(profile)
