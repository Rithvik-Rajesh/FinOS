"""Profile use cases: JIT get-or-create and updates."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.sequence import next_server_seq
from app.domain.ids import new_id
from app.modules.identity import repository as repo
from app.modules.identity.models import UserProfile
from app.modules.identity.schemas import PreferencesUpdate, ProfileUpdate


async def get_or_create(session: AsyncSession, *, user_id: uuid.UUID) -> UserProfile:
    profile = await repo.get(session, user_id)
    if profile is not None:
        return profile
    profile = UserProfile(
        id=new_id(),
        user_id=user_id,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, profile)
    await session.flush()
    return profile


async def _apply(
    session: AsyncSession, *, user_id: uuid.UUID, changes: dict[str, object]
) -> UserProfile:
    profile = await get_or_create(session, user_id=user_id)
    dirty = False
    for key, value in changes.items():
        if getattr(profile, key) != value:
            setattr(profile, key, value)
            dirty = True
    if dirty:
        profile.version += 1
        profile.server_seq = await next_server_seq(session, user_id)
        await session.flush()
    return profile


async def update_profile(
    session: AsyncSession, *, user_id: uuid.UUID, data: ProfileUpdate
) -> UserProfile:
    changes = data.model_dump(exclude_unset=True)
    if "currency" in changes and changes["currency"] is not None:
        changes["currency"] = str(changes["currency"]).upper()
    return await _apply(session, user_id=user_id, changes=changes)


async def update_preferences(
    session: AsyncSession, *, user_id: uuid.UUID, data: PreferencesUpdate
) -> UserProfile:
    return await _apply(session, user_id=user_id, changes=data.model_dump(exclude_unset=True))
