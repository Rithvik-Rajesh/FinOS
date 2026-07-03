"""Categories REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import Page
from app.modules.categories import repository as repo
from app.modules.categories import service
from app.modules.categories.schemas import CategoryCreate, CategoryOut, CategoryUpdate

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryCreate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> CategoryOut:
    category = await service.create_category(
        session, user_id=user_id, data=body, correlation_id=correlation_id
    )
    return CategoryOut.model_validate(category)


@router.get("", response_model=Page[CategoryOut])
async def list_categories(
    session: DbSession,
    user_id: CurrentUserId,
    parent_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[CategoryOut]:
    rows = await repo.list_(session, user_id, parent_id=parent_id, limit=limit, offset=offset)
    return Page(items=[CategoryOut.model_validate(r) for r in rows], has_more=len(rows) == limit)


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    correlation_id: CorrelationId,
) -> CategoryOut:
    category = await service.update_category(
        session, user_id=user_id, category_id=category_id, data=body, correlation_id=correlation_id
    )
    return CategoryOut.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_category(
        session,
        user_id=user_id,
        category_id=category_id,
        clock=clock,
        correlation_id=correlation_id,
    )
