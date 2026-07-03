"""Category use cases."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.ids import new_id
from app.modules.audit.repository import record as audit_record
from app.modules.categories import repository as repo
from app.modules.categories.models import Category
from app.modules.categories.schemas import CategoryCreate, CategoryUpdate


async def create_category(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: CategoryCreate,
    correlation_id: str | None = None,
) -> Category:
    category_id = data.id or new_id()
    existing = await repo.get(session, user_id, category_id)
    if existing is not None:
        return existing

    category = Category(
        id=category_id,
        user_id=user_id,
        name=data.name,
        parent_id=data.parent_id,
        icon=data.icon,
        color=data.color,
        is_system=False,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, category)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="category",
        entity_id=category_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name},
    )
    await session.flush()
    return category


async def update_category(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    data: CategoryUpdate,
    correlation_id: str | None = None,
) -> Category:
    category = await repo.get(session, user_id, category_id)
    if category is None:
        raise NotFoundError("category not found")

    fields = data.model_dump(exclude_unset=True)
    changes: dict[str, object] = {}
    for key, value in fields.items():
        if getattr(category, key) != value:
            changes[key] = value
            setattr(category, key, value)

    if changes:
        category.version += 1
        category.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="category",
            entity_id=category_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff=changes,
        )
        await session.flush()
    return category


async def delete_category(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    category = await repo.get(session, user_id, category_id)
    if category is None:
        raise NotFoundError("category not found")
    category.deleted_at = clock.now()
    category.version += 1
    category.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="category",
        entity_id=category_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()
