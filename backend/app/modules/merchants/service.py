"""Merchant use cases."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.ids import new_id
from app.modules.audit.repository import record as audit_record
from app.modules.merchants import repository as repo
from app.modules.merchants.models import Merchant
from app.modules.merchants.schemas import MerchantCreate, MerchantUpdate


def _normalize(name: str) -> str:
    return " ".join(name.strip().split()).casefold()


async def create_merchant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: MerchantCreate,
    correlation_id: str | None = None,
) -> Merchant:
    merchant_id = data.id or new_id()
    existing = await repo.get(session, user_id, merchant_id)
    if existing is not None:
        return existing

    merchant = Merchant(
        id=merchant_id,
        user_id=user_id,
        name=data.name.strip(),
        normalized_name=_normalize(data.name),
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, merchant)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="merchant",
        entity_id=merchant_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": merchant.name},
    )
    await session.flush()
    return merchant


async def update_merchant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    merchant_id: uuid.UUID,
    data: MerchantUpdate,
    correlation_id: str | None = None,
) -> Merchant:
    merchant = await repo.get(session, user_id, merchant_id)
    if merchant is None:
        raise NotFoundError("merchant not found")

    if data.name is not None and data.name.strip() != merchant.name:
        merchant.name = data.name.strip()
        merchant.normalized_name = _normalize(data.name)
        merchant.version += 1
        merchant.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="merchant",
            entity_id=merchant_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff={"name": merchant.name},
        )
        await session.flush()
    return merchant


async def delete_merchant(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    merchant_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    merchant = await repo.get(session, user_id, merchant_id)
    if merchant is None:
        raise NotFoundError("merchant not found")
    merchant.deleted_at = clock.now()
    merchant.version += 1
    merchant.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="merchant",
        entity_id=merchant_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()
