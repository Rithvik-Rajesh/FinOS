"""User profile data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import UserProfile


async def get(session: AsyncSession, user_id: uuid.UUID) -> UserProfile | None:
    stmt = select(UserProfile).where(
        UserProfile.user_id == user_id, UserProfile.deleted_at.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def add(session: AsyncSession, profile: UserProfile) -> None:
    session.add(profile)
