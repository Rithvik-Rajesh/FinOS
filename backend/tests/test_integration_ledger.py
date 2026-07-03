"""Integration tests for the transaction engine, balances, rules, and reporting.

Exercises the real persistence + service stack on in-memory SQLite.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.domain.enums import (
    AccountType,
    CategorizationSource,
    RuleField,
    RuleOperator,
    TransactionType,
)
from app.domain.money import Money
from app.modules.accounts import service as accounts_service
from app.modules.accounts.schemas import AccountCreate
from app.modules.categories import service as categories_service
from app.modules.categories.schemas import CategoryCreate
from app.modules.ledger import service as ledger_service
from app.modules.ledger.schemas import TransactionCreate, TransactionUpdate
from app.modules.merchants import service as merchants_service
from app.modules.merchants.schemas import MerchantCreate
from app.modules.reporting import service as reporting_service
from app.modules.rules import service as rules_service
from app.modules.rules.schemas import PredicateSchema, RuleCreate
from tests.conftest import CLOCK, OTHER_USER, TEST_USER


async def _account(session: AsyncSession, name: str = "Cash", opening: int = 0) -> uuid.UUID:
    acc = await accounts_service.create_account(
        session,
        user_id=TEST_USER,
        data=AccountCreate(
            name=name, type=AccountType.CASH, currency="INR", opening_balance_minor=opening
        ),
        clock=CLOCK,
    )
    await session.commit()
    return acc.id


def _money(minor: int) -> MoneySchema:
    return MoneySchema(amount_minor=minor, currency="INR")


async def _expense(session: AsyncSession, account_id: uuid.UUID, minor: int) -> uuid.UUID:
    txn = await ledger_service.create_transaction(
        session,
        user_id=TEST_USER,
        data=TransactionCreate(
            account_id=account_id,
            type=TransactionType.EXPENSE,
            amount=_money(minor),
            occurred_at=CLOCK.now(),
        ),
        clock=CLOCK,
    )
    await session.commit()
    return txn.id


async def _balance(session: AsyncSession, account_id: uuid.UUID) -> Money:
    from app.modules.accounts import repository as repo

    account = await repo.get(session, TEST_USER, account_id)
    assert account is not None
    return await accounts_service.get_balance(session, user_id=TEST_USER, account=account)


async def test_expense_moves_balance(session: AsyncSession) -> None:
    acc = await _account(session, opening=100000)
    await _expense(session, acc, 28000)
    assert await _balance(session, acc) == Money(72000, "INR")


async def test_transfer_is_double_entry(session: AsyncSession) -> None:
    src = await _account(session, "Savings", opening=100000)
    dst = await _account(session, "Wallet", opening=0)
    await ledger_service.create_transaction(
        session,
        user_id=TEST_USER,
        data=TransactionCreate(
            account_id=src,
            counter_account_id=dst,
            type=TransactionType.TRANSFER,
            amount=_money(30000),
            occurred_at=CLOCK.now(),
        ),
        clock=CLOCK,
    )
    await session.commit()
    assert await _balance(session, src) == Money(70000, "INR")
    assert await _balance(session, dst) == Money(30000, "INR")


async def test_update_reposts_and_keeps_balance_exact(session: AsyncSession) -> None:
    acc = await _account(session, opening=100000)
    txn_id = await _expense(session, acc, 28000)
    await ledger_service.update_transaction(
        session,
        user_id=TEST_USER,
        txn_id=txn_id,
        data=TransactionUpdate(amount=_money(30000)),
        clock=CLOCK,
    )
    await session.commit()
    # 100000 - 30000, not 100000 - 28000 - 30000.
    assert await _balance(session, acc) == Money(70000, "INR")


async def test_delete_reverses_balance(session: AsyncSession) -> None:
    acc = await _account(session, opening=100000)
    txn_id = await _expense(session, acc, 28000)
    await ledger_service.delete_transaction(session, user_id=TEST_USER, txn_id=txn_id, clock=CLOCK)
    await session.commit()
    assert await _balance(session, acc) == Money(100000, "INR")


async def test_immutable_history_entries_are_appended(session: AsyncSession) -> None:
    from app.modules.ledger import repository as repo

    acc = await _account(session, opening=100000)
    txn_id = await _expense(session, acc, 28000)
    await ledger_service.update_transaction(
        session,
        user_id=TEST_USER,
        txn_id=txn_id,
        data=TransactionUpdate(amount=_money(30000)),
        clock=CLOCK,
    )
    await session.commit()
    entries = await repo.entries_for(session, TEST_USER, txn_id)
    # original(1) + reversal(1) + new(1) = 3 immutable rows.
    assert len(entries) == 3
    assert sum(e.amount_minor for e in entries) == -30000


async def test_rule_auto_categorizes_on_create(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await categories_service.create_category(
        session, user_id=TEST_USER, data=CategoryCreate(name="Food")
    )
    swiggy = await merchants_service.create_merchant(
        session, user_id=TEST_USER, data=MerchantCreate(name="Swiggy")
    )
    await rules_service.create_rule(
        session,
        user_id=TEST_USER,
        data=RuleCreate(
            name="Swiggy is Food",
            priority=10,
            conditions=[
                PredicateSchema(field=RuleField.MERCHANT, operator=RuleOperator.EQ, value="Swiggy")
            ],
            set_category_id=food.id,
        ),
    )
    await session.commit()

    txn = await ledger_service.create_transaction(
        session,
        user_id=TEST_USER,
        data=TransactionCreate(
            account_id=acc,
            type=TransactionType.EXPENSE,
            amount=_money(28000),
            occurred_at=CLOCK.now(),
            merchant_id=swiggy.id,
        ),
        clock=CLOCK,
    )
    await session.commit()
    assert txn.category_id == food.id
    assert txn.categorization_source is CategorizationSource.USER_RULE


async def test_reporting_summary_and_spending(session: AsyncSession) -> None:
    acc = await _account(session)
    food = await categories_service.create_category(
        session, user_id=TEST_USER, data=CategoryCreate(name="Food")
    )
    await session.commit()
    for minor in (28000, 12000):
        await ledger_service.create_transaction(
            session,
            user_id=TEST_USER,
            data=TransactionCreate(
                account_id=acc,
                type=TransactionType.EXPENSE,
                amount=_money(minor),
                occurred_at=CLOCK.now(),
                category_id=food.id,
            ),
            clock=CLOCK,
        )
    await session.commit()

    spending, income, net = await reporting_service.summary(
        session, TEST_USER, currency="INR", date_from=None, date_to=None
    )
    assert spending == Money(40000, "INR")
    assert income == Money(0, "INR")
    assert net == Money(-40000, "INR")

    groups = await reporting_service.spending_by(
        session, TEST_USER, group_by="category", currency="INR", date_from=None, date_to=None
    )
    assert groups[0].key == food.id
    assert groups[0].total == Money(40000, "INR")


async def test_tenant_isolation(session: AsyncSession) -> None:
    from app.modules.accounts import repository as repo

    acc = await _account(session)
    # Another user cannot see this account.
    assert await repo.get(session, OTHER_USER, acc) is None


async def test_negative_amount_rejected(session: AsyncSession) -> None:
    from app.modules.ledger.service import TransactionInvalidError

    acc = await _account(session)
    with pytest.raises(TransactionInvalidError):
        await ledger_service.create_transaction(
            session,
            user_id=TEST_USER,
            data=TransactionCreate(
                account_id=acc,
                type=TransactionType.EXPENSE,
                amount=_money(-100),
                occurred_at=CLOCK.now(),
            ),
            clock=CLOCK,
        )
