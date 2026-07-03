"""Accounts REST API."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.schemas import MoneySchema, Page
from app.core.errors import NotFoundError
from app.modules.accounts import repository as repo
from app.modules.accounts import service
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import (
    AccountCreate,
    AccountOut,
    AccountUpdate,
    AccountWithBalance,
    ReconcileRequest,
    ReconcileResult,
)

router = APIRouter(prefix="/accounts", tags=["accounts"])


async def _with_balance(
    session: AsyncSession, user_id: uuid.UUID, account: Account
) -> AccountWithBalance:
    balance = await service.get_balance(session, user_id=user_id, account=account)
    return AccountWithBalance(
        **AccountOut.model_validate(account).model_dump(),
        balance=MoneySchema.from_money(balance),
    )


@router.post("", response_model=AccountOut, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> AccountOut:
    account = await service.create_account(
        session, user_id=user_id, data=body, clock=clock, correlation_id=correlation_id
    )
    return AccountOut.model_validate(account)


@router.get("", response_model=Page[AccountWithBalance])
async def list_accounts(
    session: DbSession,
    user_id: CurrentUserId,
    include_archived: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[AccountWithBalance]:
    accounts = await repo.list_(
        session, user_id, include_archived=include_archived, limit=limit, offset=offset
    )
    items = [await _with_balance(session, user_id, a) for a in accounts]
    return Page(items=items, has_more=len(items) == limit)


@router.get("/{account_id}", response_model=AccountWithBalance)
async def get_account(
    account_id: uuid.UUID, session: DbSession, user_id: CurrentUserId
) -> AccountWithBalance:
    account = await repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError("account not found")
    return await _with_balance(session, user_id, account)


@router.patch("/{account_id}", response_model=AccountOut)
async def update_account(
    account_id: uuid.UUID,
    body: AccountUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> AccountOut:
    account = await service.update_account(
        session,
        user_id=user_id,
        account_id=account_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return AccountOut.model_validate(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    account_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_account(
        session, user_id=user_id, account_id=account_id, clock=clock, correlation_id=correlation_id
    )


@router.post("/{account_id}/reconcile", response_model=ReconcileResult)
async def reconcile_account(
    account_id: uuid.UUID,
    body: ReconcileRequest,
    session: DbSession,
    user_id: CurrentUserId,
) -> ReconcileResult:
    account = await repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError("account not found")
    computed = await service.get_balance(session, user_id=user_id, account=account)
    statement = body.statement_balance.to_money()
    difference = statement - computed
    return ReconcileResult(
        computed_balance=MoneySchema.from_money(computed),
        statement_balance=MoneySchema.from_money(statement),
        difference=MoneySchema.from_money(difference),
    )
