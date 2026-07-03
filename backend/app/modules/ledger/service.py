"""The transaction engine.

Owns the full lifecycle of a transaction: validation, posting to the immutable ledger,
rule-based categorization, audit, and event emission. Edits and deletes never mutate
existing ledger entries — they append reversing entries and (for edits) new ones, so
account balances stay exact and the financial history is preserved (TRANSACTION_ENGINE.md).
"""

from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MoneySchema
from app.core.errors import AppError, NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.enums import CategorizationSource, TransactionType
from app.domain.events import (
    RuleApplied,
    TransactionCreated,
    TransactionDeleted,
    TransactionUpdated,
)
from app.domain.ids import new_id
from app.domain.ledger import Posting, PostingError, TransactionInput, build_postings
from app.domain.money import Money
from app.events.outbox import enqueue
from app.modules.accounts import repository as accounts_repo
from app.modules.audit.repository import record as audit_record
from app.modules.ledger import repository as repo
from app.modules.ledger.facts import build_facts
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.ledger.schemas import TransactionCreate, TransactionUpdate
from app.modules.merchants import repository as merchants_repo
from app.modules.rules import service as rules_service

_MONEY_FIELDS = ("account_id", "type", "amount", "counter_account_id")


class TransactionInvalidError(AppError):
    status_code = 422
    code = "transaction_invalid"


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=dt.UTC)


def _entries(
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    postings: Sequence[Posting],
    txn_version: int,
    *,
    is_reversal: bool,
) -> list[LedgerEntry]:
    return [
        LedgerEntry(
            id=new_id(),
            user_id=user_id,
            transaction_id=txn_id,
            account_id=p.account_id,
            amount_minor=p.amount.amount_minor,
            currency=p.amount.currency,
            txn_version=txn_version,
            is_reversal=is_reversal,
        )
        for p in postings
    ]


def _reversal(
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    old_entries: Sequence[LedgerEntry],
    txn_version: int,
) -> list[LedgerEntry]:
    return [
        LedgerEntry(
            id=new_id(),
            user_id=user_id,
            transaction_id=txn_id,
            account_id=e.account_id,
            amount_minor=-e.amount_minor,
            currency=e.currency,
            txn_version=txn_version,
            is_reversal=True,
        )
        for e in old_entries
    ]


async def _validate_and_post(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    txn_type: TransactionType,
    amount: Money,
    account_id: uuid.UUID,
    counter_account_id: uuid.UUID | None,
) -> list[Posting]:
    account = await accounts_repo.get(session, user_id, account_id)
    if account is None:
        raise TransactionInvalidError("account not found")
    if amount.currency != account.currency:
        raise TransactionInvalidError("amount currency must match the account currency")

    if txn_type is TransactionType.TRANSFER:
        if counter_account_id is None:
            raise TransactionInvalidError("transfer requires counter_account_id")
        counter = await accounts_repo.get(session, user_id, counter_account_id)
        if counter is None:
            raise TransactionInvalidError("counter account not found")
        if counter.currency != amount.currency:
            raise TransactionInvalidError("transfer accounts must share a currency")

    try:
        return build_postings(
            TransactionInput(
                type=txn_type,
                amount=amount,
                account_id=account_id,
                counter_account_id=counter_account_id,
            )
        )
    except PostingError as exc:
        raise TransactionInvalidError(str(exc)) from exc


async def create_transaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: TransactionCreate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Transaction:
    amount = data.amount.to_money()
    occurred_at = _aware(data.occurred_at)
    postings = await _validate_and_post(
        session,
        user_id,
        txn_type=data.type,
        amount=amount,
        account_id=data.account_id,
        counter_account_id=data.counter_account_id,
    )

    category_id = data.category_id
    merchant_id = data.merchant_id
    categorization_source = (
        CategorizationSource.MANUAL if category_id is not None else CategorizationSource.DEFAULT
    )
    matched_rule_ids: tuple[uuid.UUID, ...] = ()

    if category_id is None:
        account = await accounts_repo.get(session, user_id, data.account_id)
        merchant_name = None
        if merchant_id is not None:
            merchant = await merchants_repo.get(session, user_id, merchant_id)
            merchant_name = merchant.name if merchant is not None else None
        facts = build_facts(
            type=data.type,
            amount_minor=amount.amount_minor,
            currency=amount.currency,
            occurred_at=occurred_at,
            merchant_name=merchant_name,
            account_name=account.name if account is not None else None,
            counterparty=data.counterparty,
            note=data.note,
        )
        result = await rules_service.categorize(session, user_id, facts)
        if result.category_id is not None:
            category_id = result.category_id
        if merchant_id is None and result.merchant_id is not None:
            merchant_id = result.merchant_id
        categorization_source = result.source
        matched_rule_ids = result.matched_rule_ids

    txn_id = data.id or new_id()
    existing = await repo.get(session, user_id, txn_id, include_deleted=True)
    if existing is not None:
        return existing  # idempotent offline replay

    txn = Transaction(
        id=txn_id,
        user_id=user_id,
        account_id=data.account_id,
        counter_account_id=data.counter_account_id,
        type=data.type,
        status=data.status,
        amount_minor=amount.amount_minor,
        currency=amount.currency,
        occurred_at=occurred_at,
        category_id=category_id,
        merchant_id=merchant_id,
        counterparty=data.counterparty,
        note=data.note,
        source=data.source,
        categorization_source=categorization_source,
        external_ref=data.external_ref,
        related_transaction_id=data.related_transaction_id,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, txn)
    repo.add_entries(session, _entries(user_id, txn_id, postings, 1, is_reversal=False))
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="transaction",
        entity_id=txn_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"type": data.type.value, "amount_minor": amount.amount_minor},
    )
    enqueue(
        session,
        TransactionCreated(
            user_id=user_id,
            occurred_at=clock.now(),
            transaction_id=txn_id,
            type=data.type,
            amount_minor=amount.amount_minor,
            currency=amount.currency,
            account_id=data.account_id,
            category_id=category_id,
            merchant_id=merchant_id,
        ),
    )
    if matched_rule_ids:
        enqueue(
            session,
            RuleApplied(
                user_id=user_id,
                occurred_at=clock.now(),
                transaction_id=txn_id,
                rule_ids=matched_rule_ids,
                category_id=category_id,
                source=categorization_source,
            ),
        )
    await session.flush()
    return txn


async def update_transaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    data: TransactionUpdate,
    clock: Clock,
    correlation_id: str | None = None,
) -> Transaction:
    txn = await repo.get(session, user_id, txn_id)
    if txn is None:
        raise NotFoundError("transaction not found")

    fields = data.model_dump(exclude_unset=True)
    money_changed = any(k in fields for k in _MONEY_FIELDS)
    changed: list[str] = []

    # Metadata-only fields apply directly.
    for key in ("occurred_at", "category_id", "merchant_id", "counterparty", "note", "status"):
        if key in fields:
            value = _aware(fields[key]) if key == "occurred_at" else fields[key]
            if getattr(txn, key) != value:
                setattr(txn, key, value)
                changed.append(key)

    new_postings: list[Posting] | None = None
    if money_changed:
        new_type = fields.get("type", txn.type)
        new_account_id = fields.get("account_id", txn.account_id)
        new_counter_id = fields.get("counter_account_id", txn.counter_account_id)
        amount = (
            MoneySchema.model_validate(fields["amount"]).to_money()
            if "amount" in fields
            else Money(txn.amount_minor, txn.currency)
        )
        new_postings = await _validate_and_post(
            session,
            user_id,
            txn_type=new_type,
            amount=amount,
            account_id=new_account_id,
            counter_account_id=new_counter_id,
        )
        txn.type = new_type
        txn.account_id = new_account_id
        txn.counter_account_id = new_counter_id
        txn.amount_minor = amount.amount_minor
        txn.currency = amount.currency
        changed.extend(k for k in _MONEY_FIELDS if k in fields)

    if not changed:
        return txn  # no-op

    txn.version += 1
    if new_postings is not None:
        old_entries = await repo.entries_for(session, user_id, txn_id)
        repo.add_entries(session, _reversal(user_id, txn_id, old_entries, txn.version))
        repo.add_entries(
            session, _entries(user_id, txn_id, new_postings, txn.version, is_reversal=False)
        )
    txn.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="update",
        entity_type="transaction",
        entity_id=txn_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"changed": changed},
    )
    enqueue(
        session,
        TransactionUpdated(
            user_id=user_id,
            occurred_at=clock.now(),
            transaction_id=txn_id,
            version=txn.version,
            changed_fields=tuple(changed),
        ),
    )
    await session.flush()
    return txn


async def delete_transaction(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    txn_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    txn = await repo.get(session, user_id, txn_id)
    if txn is None:
        raise NotFoundError("transaction not found")

    old_entries = await repo.entries_for(session, user_id, txn_id)
    txn.version += 1
    repo.add_entries(session, _reversal(user_id, txn_id, old_entries, txn.version))
    txn.deleted_at = clock.now()
    txn.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="transaction",
        entity_id=txn_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    enqueue(
        session,
        TransactionDeleted(user_id=user_id, occurred_at=clock.now(), transaction_id=txn_id),
    )
    await session.flush()


async def get_transaction(
    session: AsyncSession, *, user_id: uuid.UUID, txn_id: uuid.UUID
) -> Transaction:
    txn = await repo.get(session, user_id, txn_id)
    if txn is None:
        raise NotFoundError("transaction not found")
    return txn
