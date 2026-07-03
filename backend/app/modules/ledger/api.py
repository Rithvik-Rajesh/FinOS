"""Transactions REST API — the ledger surface with filtering, sorting, pagination."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status

from app.api.deps import ClockDep, CorrelationId, CurrentUserId, DbSession
from app.api.pagination import decode_cursor, encode_cursor
from app.api.schemas import Page
from app.domain.enums import TransactionStatus, TransactionType
from app.modules.ledger import repository as repo
from app.modules.ledger import service
from app.modules.ledger.models import Transaction
from app.modules.ledger.schemas import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    body: TransactionCreate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> TransactionOut:
    txn = await service.create_transaction(
        session, user_id=user_id, data=body, clock=clock, correlation_id=correlation_id
    )
    return TransactionOut.from_model(txn)


@router.get("", response_model=Page[TransactionOut])
async def list_transactions(
    session: DbSession,
    user_id: CurrentUserId,
    date_from: Annotated[dt.datetime | None, Query(alias="from")] = None,
    date_to: Annotated[dt.datetime | None, Query(alias="to")] = None,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    merchant_id: uuid.UUID | None = None,
    type_: Annotated[TransactionType | None, Query(alias="type")] = None,
    status_: Annotated[TransactionStatus | None, Query(alias="status")] = None,
    sort: Literal["occurred_at", "amount"] = "occurred_at",
    order: Literal["asc", "desc"] = "desc",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Page[TransactionOut]:
    decoded = decode_cursor(cursor) if cursor else None
    rows, has_more = await repo.list_(
        session,
        user_id,
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        category_id=category_id,
        merchant_id=merchant_id,
        type_=type_,
        status=status_,
        sort=sort,
        order=order,
        cursor=decoded,
        limit=limit,
    )
    next_cursor = _next_cursor(rows, sort) if has_more else None
    return Page(
        items=[TransactionOut.from_model(t) for t in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _next_cursor(rows: list[Transaction], sort: str) -> str | None:
    if not rows:
        return None
    last = rows[-1]
    key = last.occurred_at.isoformat() if sort == "occurred_at" else last.amount_minor
    return encode_cursor({"k": key, "id": str(last.id)})


@router.get("/{txn_id}", response_model=TransactionOut)
async def get_transaction(
    txn_id: uuid.UUID, session: DbSession, user_id: CurrentUserId
) -> TransactionOut:
    txn = await service.get_transaction(session, user_id=user_id, txn_id=txn_id)
    return TransactionOut.from_model(txn)


@router.patch("/{txn_id}", response_model=TransactionOut)
async def update_transaction(
    txn_id: uuid.UUID,
    body: TransactionUpdate,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> TransactionOut:
    txn = await service.update_transaction(
        session,
        user_id=user_id,
        txn_id=txn_id,
        data=body,
        clock=clock,
        correlation_id=correlation_id,
    )
    return TransactionOut.from_model(txn)


@router.delete("/{txn_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    txn_id: uuid.UUID,
    session: DbSession,
    user_id: CurrentUserId,
    clock: ClockDep,
    correlation_id: CorrelationId,
) -> None:
    await service.delete_transaction(
        session, user_id=user_id, txn_id=txn_id, clock=clock, correlation_id=correlation_id
    )
