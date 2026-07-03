"""Sync engine: pull (delta), push (with conflict detection), full-sync recovery.

Cursor: every syncable write is stamped with a per-user monotonic `server_seq`. A pull
returns everything with `server_seq > since` (across all syncable entities), so
`since=0` is a full-sync recovery and `since>0` is incremental. Push applies client
mutations, detecting version conflicts and resolving last-writer-wins (the server row is
returned so the client can reconcile). See SYNC_ARCHITECTURE.md.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.sequence import SyncSequence
from app.domain.clock import Clock
from app.modules.accounts import repository as accounts_repo
from app.modules.accounts import service as accounts_service
from app.modules.accounts.models import Account
from app.modules.accounts.schemas import AccountCreate, AccountOut, AccountUpdate
from app.modules.budgets import repository as budgets_repo
from app.modules.budgets import service as budgets_service
from app.modules.budgets.models import Budget
from app.modules.budgets.schemas import BudgetCreate, BudgetOut, BudgetUpdate
from app.modules.categories import repository as categories_repo
from app.modules.categories import service as categories_service
from app.modules.categories.models import Category
from app.modules.categories.schemas import CategoryCreate, CategoryOut, CategoryUpdate
from app.modules.goals import repository as goals_repo
from app.modules.goals import service as goals_service
from app.modules.goals.models import Goal
from app.modules.goals.schemas import GoalCreate, GoalOut, GoalUpdate
from app.modules.identity import repository as identity_repo
from app.modules.identity import service as identity_service
from app.modules.identity.models import UserProfile
from app.modules.identity.schemas import ProfileOut, ProfileUpdate
from app.modules.ledger import repository as ledger_repo
from app.modules.ledger import service as ledger_service
from app.modules.ledger.models import Transaction
from app.modules.ledger.schemas import TransactionCreate, TransactionOut, TransactionUpdate
from app.modules.merchants import repository as merchants_repo
from app.modules.merchants import service as merchants_service
from app.modules.merchants.models import Merchant
from app.modules.merchants.schemas import MerchantCreate, MerchantOut, MerchantUpdate
from app.modules.recurring import repository as recurring_repo
from app.modules.recurring import service as recurring_service
from app.modules.recurring.models import RecurringSeries
from app.modules.recurring.schemas import SeriesCreate, SeriesOut, SeriesUpdate
from app.modules.rules import repository as rules_repo
from app.modules.rules import service as rules_service
from app.modules.rules.models import CategorizationRule
from app.modules.rules.schemas import RuleCreate, RuleOut, RuleUpdate
from app.modules.sync.schemas import (
    SyncChange,
    SyncEntity,
    SyncMutation,
    SyncMutationResult,
    SyncPullResponse,
    SyncPushResponse,
)


def _serialize(entity: SyncEntity, row: Any) -> dict[str, Any] | None:
    """Serialize a row for the wire, or None when it is a tombstone."""
    if row.deleted_at is not None:
        return None
    if entity == "accounts":
        return AccountOut.model_validate(row).model_dump(mode="json")
    if entity == "categories":
        return CategoryOut.model_validate(row).model_dump(mode="json")
    if entity == "merchants":
        return MerchantOut.model_validate(row).model_dump(mode="json")
    if entity == "rules":
        return RuleOut.model_validate(row).model_dump(mode="json")
    if entity == "goals":
        return GoalOut.model_validate(row).model_dump(mode="json")
    if entity == "budgets":
        return BudgetOut.model_validate(row).model_dump(mode="json")
    if entity == "recurring":
        return SeriesOut.model_validate(row).model_dump(mode="json")
    if entity == "profiles":
        return ProfileOut.model_validate(row).model_dump(mode="json")
    return TransactionOut.from_model(row).model_dump(mode="json")


async def pull(
    session: AsyncSession, user_id: uuid.UUID, *, since: int, limit: int
) -> SyncPullResponse:
    collected: list[tuple[int, SyncChange]] = []

    async def gather(entity: SyncEntity, rows: list[Any]) -> None:
        for row in rows:
            collected.append(
                (
                    row.server_seq,
                    SyncChange(
                        entity=entity,
                        id=row.id,
                        server_seq=row.server_seq,
                        version=row.version,
                        deleted=row.deleted_at is not None,
                        data=_serialize(entity, row),
                    ),
                )
            )

    await gather("accounts", await _changed(session, Account, user_id, since, limit))
    await gather("categories", await _changed(session, Category, user_id, since, limit))
    await gather("merchants", await _changed(session, Merchant, user_id, since, limit))
    await gather("rules", await _changed(session, CategorizationRule, user_id, since, limit))
    await gather("transactions", await _changed(session, Transaction, user_id, since, limit))
    await gather("goals", await _changed(session, Goal, user_id, since, limit))
    await gather("budgets", await _changed(session, Budget, user_id, since, limit))
    await gather("recurring", await _changed(session, RecurringSeries, user_id, since, limit))
    await gather("profiles", await _changed(session, UserProfile, user_id, since, limit))

    collected.sort(key=lambda item: item[0])
    has_more = len(collected) > limit
    changes = [change for _, change in collected[:limit]]
    next_cursor = changes[-1].server_seq if changes else since
    return SyncPullResponse(changes=changes, next_cursor=next_cursor, has_more=has_more)


async def _changed(
    session: AsyncSession, model: Any, user_id: uuid.UUID, since: int, limit: int
) -> list[Any]:
    stmt = (
        select(model)
        .where(model.user_id == user_id, model.server_seq > since)
        .order_by(model.server_seq)
        .limit(limit + 1)
    )
    return list((await session.execute(stmt)).scalars().all())


async def _get_active(
    session: AsyncSession, user_id: uuid.UUID, entity: SyncEntity, entity_id: uuid.UUID
) -> Any:
    if entity == "accounts":
        return await accounts_repo.get(session, user_id, entity_id)
    if entity == "categories":
        return await categories_repo.get(session, user_id, entity_id)
    if entity == "merchants":
        return await merchants_repo.get(session, user_id, entity_id)
    if entity == "rules":
        return await rules_repo.get(session, user_id, entity_id)
    if entity == "goals":
        return await goals_repo.get(session, user_id, entity_id)
    if entity == "budgets":
        return await budgets_repo.get(session, user_id, entity_id)
    if entity == "recurring":
        return await recurring_repo.get(session, user_id, entity_id)
    if entity == "profiles":
        return await identity_repo.get(session, user_id)  # per-user singleton
    return await ledger_repo.get(session, user_id, entity_id)


async def _apply_upsert(
    session: AsyncSession,
    user_id: uuid.UUID,
    mutation: SyncMutation,
    *,
    exists: bool,
    clock: Clock,
    correlation_id: str | None,
) -> Any:
    data = mutation.data or {}
    entity = mutation.entity
    eid = mutation.id
    if entity == "accounts":
        if not exists:
            return await accounts_service.create_account(
                session,
                user_id=user_id,
                data=AccountCreate.model_validate({**data, "id": str(eid)}),
                clock=clock,
                correlation_id=correlation_id,
            )
        return await accounts_service.update_account(
            session,
            user_id=user_id,
            account_id=eid,
            data=AccountUpdate.model_validate(data),
            clock=clock,
            correlation_id=correlation_id,
        )
    if entity == "categories":
        if not exists:
            return await categories_service.create_category(
                session,
                user_id=user_id,
                data=CategoryCreate.model_validate({**data, "id": str(eid)}),
                correlation_id=correlation_id,
            )
        return await categories_service.update_category(
            session,
            user_id=user_id,
            category_id=eid,
            data=CategoryUpdate.model_validate(data),
            correlation_id=correlation_id,
        )
    if entity == "merchants":
        if not exists:
            return await merchants_service.create_merchant(
                session,
                user_id=user_id,
                data=MerchantCreate.model_validate({**data, "id": str(eid)}),
                correlation_id=correlation_id,
            )
        return await merchants_service.update_merchant(
            session,
            user_id=user_id,
            merchant_id=eid,
            data=MerchantUpdate.model_validate(data),
            correlation_id=correlation_id,
        )
    if entity == "rules":
        if not exists:
            return await rules_service.create_rule(
                session,
                user_id=user_id,
                data=RuleCreate.model_validate({**data, "id": str(eid)}),
                correlation_id=correlation_id,
            )
        return await rules_service.update_rule(
            session,
            user_id=user_id,
            rule_id=eid,
            data=RuleUpdate.model_validate(data),
            correlation_id=correlation_id,
        )
    if entity == "goals":
        if not exists:
            return await goals_service.create_goal(
                session,
                user_id=user_id,
                data=GoalCreate.model_validate({**data, "id": str(eid)}),
                correlation_id=correlation_id,
            )
        return await goals_service.update_goal(
            session,
            user_id=user_id,
            goal_id=eid,
            data=GoalUpdate.model_validate(data),
            clock=clock,
            correlation_id=correlation_id,
        )
    if entity == "budgets":
        if not exists:
            return await budgets_service.create_budget(
                session,
                user_id=user_id,
                data=BudgetCreate.model_validate({**data, "id": str(eid)}),
                correlation_id=correlation_id,
            )
        return await budgets_service.update_budget(
            session,
            user_id=user_id,
            budget_id=eid,
            data=BudgetUpdate.model_validate(data),
            clock=clock,
            correlation_id=correlation_id,
        )
    if entity == "recurring":
        if not exists:
            return await recurring_service.create_series(
                session,
                user_id=user_id,
                data=SeriesCreate.model_validate({**data, "id": str(eid)}),
                clock=clock,
                correlation_id=correlation_id,
            )
        return await recurring_service.update_series(
            session,
            user_id=user_id,
            series_id=eid,
            data=SeriesUpdate.model_validate(data),
            clock=clock,
            correlation_id=correlation_id,
        )
    if entity == "profiles":
        # Profile is a per-user singleton: upsert always maps to an update.
        return await identity_service.update_profile(
            session, user_id=user_id, data=ProfileUpdate.model_validate(data)
        )
    if not exists:
        return await ledger_service.create_transaction(
            session,
            user_id=user_id,
            data=TransactionCreate.model_validate({**data, "id": str(eid)}),
            clock=clock,
            correlation_id=correlation_id,
        )
    return await ledger_service.update_transaction(
        session,
        user_id=user_id,
        txn_id=eid,
        data=TransactionUpdate.model_validate(data),
        clock=clock,
        correlation_id=correlation_id,
    )


async def _apply_delete(
    session: AsyncSession,
    user_id: uuid.UUID,
    entity: SyncEntity,
    entity_id: uuid.UUID,
    *,
    clock: Clock,
    correlation_id: str | None,
) -> None:
    if entity == "accounts":
        await accounts_service.delete_account(
            session,
            user_id=user_id,
            account_id=entity_id,
            clock=clock,
            correlation_id=correlation_id,
        )
    elif entity == "categories":
        await categories_service.delete_category(
            session,
            user_id=user_id,
            category_id=entity_id,
            clock=clock,
            correlation_id=correlation_id,
        )
    elif entity == "merchants":
        await merchants_service.delete_merchant(
            session,
            user_id=user_id,
            merchant_id=entity_id,
            clock=clock,
            correlation_id=correlation_id,
        )
    elif entity == "rules":
        await rules_service.delete_rule(
            session, user_id=user_id, rule_id=entity_id, clock=clock, correlation_id=correlation_id
        )
    elif entity == "goals":
        await goals_service.delete_goal(
            session, user_id=user_id, goal_id=entity_id, clock=clock, correlation_id=correlation_id
        )
    elif entity == "budgets":
        await budgets_service.delete_budget(
            session,
            user_id=user_id,
            budget_id=entity_id,
            clock=clock,
            correlation_id=correlation_id,
        )
    elif entity == "recurring":
        await recurring_service.delete_series(
            session,
            user_id=user_id,
            series_id=entity_id,
            clock=clock,
            correlation_id=correlation_id,
        )
    elif entity == "profiles":
        raise AppError("profiles cannot be deleted via sync")
    else:
        await ledger_service.delete_transaction(
            session, user_id=user_id, txn_id=entity_id, clock=clock, correlation_id=correlation_id
        )


async def _current_cursor(session: AsyncSession, user_id: uuid.UUID) -> int:
    row = await session.get(SyncSequence, user_id)
    return (row.next_seq - 1) if row is not None else 0


async def push(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    mutations: list[SyncMutation],
    clock: Clock,
    correlation_id: str | None,
) -> SyncPushResponse:
    results: list[SyncMutationResult] = []

    for mutation in mutations:
        try:
            existing = await _get_active(session, user_id, mutation.entity, mutation.id)
            conflict = (
                existing is not None
                and mutation.base_version is not None
                and existing.version != mutation.base_version
            )
            if conflict:
                results.append(
                    SyncMutationResult(
                        id=mutation.id,
                        entity=mutation.entity,
                        status="conflict",
                        server_seq=existing.server_seq,
                        version=existing.version,
                        server_data=_serialize(mutation.entity, existing),
                    )
                )
                continue

            if mutation.op == "delete":
                if existing is None:
                    results.append(
                        SyncMutationResult(id=mutation.id, entity=mutation.entity, status="applied")
                    )
                    continue
                await _apply_delete(
                    session,
                    user_id,
                    mutation.entity,
                    mutation.id,
                    clock=clock,
                    correlation_id=correlation_id,
                )
                results.append(
                    SyncMutationResult(id=mutation.id, entity=mutation.entity, status="applied")
                )
                continue

            row = await _apply_upsert(
                session,
                user_id,
                mutation,
                exists=existing is not None,
                clock=clock,
                correlation_id=correlation_id,
            )
            results.append(
                SyncMutationResult(
                    id=mutation.id,
                    entity=mutation.entity,
                    status="applied",
                    server_seq=row.server_seq,
                    version=row.version,
                    server_data=_serialize(mutation.entity, row),
                )
            )
        except AppError as exc:
            results.append(
                SyncMutationResult(
                    id=mutation.id,
                    entity=mutation.entity,
                    status="error",
                    message=exc.message,
                )
            )

    next_cursor = await _current_cursor(session, user_id)
    return SyncPushResponse(results=results, next_cursor=next_cursor)
