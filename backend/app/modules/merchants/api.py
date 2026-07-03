"""Merchants REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import Page
from app.modules.merchants import repository as repo
from app.modules.merchants import service
from app.modules.merchants.schemas import MerchantCreate, MerchantOut, MerchantUpdate

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.post("", response_model=MerchantOut, status_code=status.HTTP_201_CREATED)
async def create_merchant(
    body: MerchantCreate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> MerchantOut:
    merchant = await service.create_merchant(
        session, user_id=user_id, data=body, correlation_id=correlation_id
    )
    return MerchantOut.model_validate(merchant)


@router.get("", response_model=Page[MerchantOut])
async def list_merchants(
    session: DbSession,
    user_id: CurrentUserId,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[MerchantOut]:
    rows = await repo.list_(session, user_id, query=q, limit=limit, offset=offset)
    return Page(items=[MerchantOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.patch("/{merchant_id}", response_model=MerchantOut)
async def update_merchant(
    merchant_id: uuid.UUID,
    body: MerchantUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> MerchantOut:
    merchant = await service.update_merchant(
        session, user_id=user_id, merchant_id=merchant_id, data=body, correlation_id=correlation_id
    )
    return MerchantOut.model_validate(merchant)


@router.delete("/{merchant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_merchant(
    merchant_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_merchant(
        session,
        user_id=user_id,
        merchant_id=merchant_id,
        clock=clock,
        correlation_id=correlation_id,
    )
