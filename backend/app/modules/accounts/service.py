"""Account use cases: create, update, soft-delete, balance, reconcile.

Orchestrates persistence + server_seq allocation + audit + events. Assumes it runs
inside the request's transaction; it flushes (to populate defaults) but never commits.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.events import AccountCreated
from app.domain.ids import new_id
from app.domain.money import Money
from app.events.outbox import enqueue
from app.modules.accounts import repository as repo
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate, AccountUpdate
from app.modules.audit.repository import record as audit_record
from app.modules.ledger.balances import account_balance


async def create_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: AccountCreate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Account:
    account_id = data.id or new_id()

    existing = await repo.get(session, user_id, account_id, include_deleted=True)
    if existing is not None:
        return existing  # idempotent create (safe offline replay)

    seq = await next_server_seq(session, user_id)
    account = Account(
        id=account_id,
        user_id=user_id,
        name=data.name,
        type=data.type,
        currency=data.currency.upper(),
        opening_balance_minor=data.opening_balance_minor,
        institution=data.institution,
        is_archived=False,
        version=1,
        server_seq=seq,
    )
    repo.add(session, account)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="account",
        entity_id=account_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name, "type": data.type.value, "currency": account.currency},
    )
    enqueue(
        session,
        AccountCreated(
            user_id=user_id,
            occurred_at=clock.now(),
            account_id=account_id,
            type=data.type.value,
            currency=account.currency,
        ),
    )
    await session.flush()
    return account


async def update_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    data: AccountUpdate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Account:
    account = await repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError("account not found")

    changes: dict[str, object] = {}
    if data.name is not None and data.name != account.name:
        changes["name"] = data.name
        account.name = data.name
    if data.is_archived is not None and data.is_archived != account.is_archived:
        changes["is_archived"] = data.is_archived
        account.is_archived = data.is_archived
    if data.institution is not None and data.institution != account.institution:
        changes["institution"] = data.institution
        account.institution = data.institution

    if changes:
        account.version += 1
        account.server_seq = await next_server_seq(session, user_id)
        audit_record(
            session,
            user_id=user_id,
            action="update",
            entity_type="account",
            entity_id=account_id,
            actor_id=user_id,
            correlation_id=correlation_id,
            diff=changes,
        )
        await session.flush()
    return account


async def delete_account(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    account = await repo.get(session, user_id, account_id)
    if account is None:
        raise NotFoundError("account not found")
    account.deleted_at = clock.now()
    account.version += 1
    account.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="account",
        entity_id=account_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()


async def get_balance(session: AsyncSession, *, user_id: uuid.UUID, account: Account) -> Money:
    return await account_balance(
        session,
        user_id,
        account.id,
        opening_minor=account.opening_balance_minor,
        currency=account.currency,
    )
