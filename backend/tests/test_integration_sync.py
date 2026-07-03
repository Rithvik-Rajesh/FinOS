"""Integration tests for the sync engine: pull, push, conflict detection, recovery."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.domain.enums import AccountType, TransactionType
from app.domain.ids import new_id
from app.modules.accounts import service as accounts_service
from app.modules.accounts.schemas import AccountCreate
from app.modules.ledger import service as ledger_service
from app.modules.ledger.schemas import TransactionCreate
from app.modules.sync import service as sync_service
from app.modules.sync.schemas import SyncMutation
from tests.conftest import CLOCK, TEST_USER


async def _seed(session: AsyncSession) -> uuid.UUID:
    acc = await accounts_service.create_account(
        session,
        user_id=TEST_USER,
        data=AccountCreate(name="Cash", type=AccountType.CASH, currency="INR"),
        clock=CLOCK,
    )
    await ledger_service.create_transaction(
        session,
        user_id=TEST_USER,
        data=TransactionCreate(
            account_id=acc.id,
            type=TransactionType.EXPENSE,
            amount=MoneySchema(amount_minor=28000, currency="INR"),
            occurred_at=CLOCK.now(),
        ),
        clock=CLOCK,
    )
    await session.commit()
    return acc.id


async def test_full_pull_returns_all(session: AsyncSession) -> None:
    await _seed(session)
    result = await sync_service.pull(session, TEST_USER, since=0, limit=500)
    entities = {c.entity for c in result.changes}
    assert "accounts" in entities
    assert "transactions" in entities
    assert result.next_cursor > 0


async def test_incremental_pull_is_empty_after_catch_up(session: AsyncSession) -> None:
    await _seed(session)
    first = await sync_service.pull(session, TEST_USER, since=0, limit=500)
    second = await sync_service.pull(session, TEST_USER, since=first.next_cursor, limit=500)
    assert second.changes == []
    assert second.has_more is False


async def test_push_creates_and_is_pullable(session: AsyncSession) -> None:
    new_account_id = new_id()
    push = await sync_service.push(
        session,
        TEST_USER,
        mutations=[
            SyncMutation(
                op="upsert",
                entity="accounts",
                id=new_account_id,
                base_version=None,
                data={"name": "Wallet", "type": "wallet", "currency": "INR"},
            )
        ],
        clock=CLOCK,
        correlation_id=None,
    )
    await session.commit()
    assert push.results[0].status == "applied"

    pulled = await sync_service.pull(session, TEST_USER, since=0, limit=500)
    ids = {c.id for c in pulled.changes}
    assert new_account_id in ids


async def test_push_detects_version_conflict(session: AsyncSession) -> None:
    acc = await accounts_service.create_account(
        session,
        user_id=TEST_USER,
        data=AccountCreate(name="Cash", type=AccountType.CASH, currency="INR"),
        clock=CLOCK,
    )
    await session.commit()

    push = await sync_service.push(
        session,
        TEST_USER,
        mutations=[
            SyncMutation(
                op="upsert",
                entity="accounts",
                id=acc.id,
                base_version=99,  # stale
                data={"name": "Renamed"},
            )
        ],
        clock=CLOCK,
        correlation_id=None,
    )
    result = push.results[0]
    assert result.status == "conflict"
    assert result.server_data is not None
    assert result.server_data["name"] == "Cash"  # server wins; client reconciles


async def test_push_delete_produces_tombstone(session: AsyncSession) -> None:
    acc = await accounts_service.create_account(
        session,
        user_id=TEST_USER,
        data=AccountCreate(name="Cash", type=AccountType.CASH, currency="INR"),
        clock=CLOCK,
    )
    await session.commit()

    await sync_service.push(
        session,
        TEST_USER,
        mutations=[SyncMutation(op="delete", entity="accounts", id=acc.id, base_version=1)],
        clock=CLOCK,
        correlation_id=None,
    )
    await session.commit()

    pulled = await sync_service.pull(session, TEST_USER, since=0, limit=500)
    tombstone = next(c for c in pulled.changes if c.id == acc.id)
    assert tombstone.deleted is True
    assert tombstone.data is None
