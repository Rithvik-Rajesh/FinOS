"""Rule use cases: CRUD, ORM<->domain mapping, live categorization, simulation, testing.

The engine itself is pure (`app.domain.rules`). This service adapts persisted rules to
domain `RuleDefinition`s, validates them, and exposes categorization to the ledger and
simulation/testing to the API.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, NotFoundError
from app.db.sequence import next_server_seq
from app.domain.clock import Clock
from app.domain.enums import RuleField, RuleOperator
from app.domain.ids import new_id
from app.domain.rules import (
    CategorizationResult,
    Predicate,
    RuleBasedCategorizer,
    RuleDefinition,
    RuleValidationError,
    TransactionFacts,
    check_rule,
    validate_rule,
)
from app.modules.audit.repository import record as audit_record
from app.modules.ledger.facts import recent_facts
from app.modules.rules import repository as repo
from app.modules.rules.models import CategorizationRule
from app.modules.rules.schemas import RuleCreate, RuleUpdate


class RuleInvalidError(AppError):
    status_code = 422
    code = "rule_invalid"


def _predicates_from_conditions(conditions: Sequence[dict[str, Any]]) -> tuple[Predicate, ...]:
    return tuple(
        Predicate(
            field=RuleField(cond["field"]),
            operator=RuleOperator(cond["operator"]),
            value=cond["value"],
        )
        for cond in conditions
    )


def _rule_to_domain(rule: CategorizationRule) -> RuleDefinition:
    return RuleDefinition(
        id=rule.id,
        priority=rule.priority,
        predicates=_predicates_from_conditions(rule.conditions),
        logic=rule.logic,
        set_category_id=rule.set_category_id,
        set_merchant_id=rule.set_merchant_id,
        tags=tuple(rule.tags),
        stop_processing=rule.stop_processing,
        is_active=rule.is_active,
    )


def _draft_to_domain(data: RuleCreate) -> RuleDefinition:
    return RuleDefinition(
        id=data.id or new_id(),
        priority=data.priority,
        predicates=tuple(
            Predicate(field=c.field, operator=c.operator, value=c.value) for c in data.conditions
        ),
        logic=data.logic,
        set_category_id=data.set_category_id,
        set_merchant_id=data.set_merchant_id,
        tags=tuple(data.tags),
        stop_processing=data.stop_processing,
        is_active=data.is_active,
    )


def _validate_or_raise(definition: RuleDefinition) -> None:
    try:
        validate_rule(definition)
    except RuleValidationError as exc:
        raise RuleInvalidError(str(exc)) from exc


async def load_domain_rules(
    session: AsyncSession, user_id: uuid.UUID, *, active_only: bool = True
) -> list[RuleDefinition]:
    rules = await repo.list_(session, user_id, active_only=active_only)
    return [_rule_to_domain(r) for r in rules]


async def categorize(
    session: AsyncSession, user_id: uuid.UUID, facts: TransactionFacts
) -> CategorizationResult:
    """Apply the user's active rules to one transaction's facts (used by the ledger)."""
    categorizer = RuleBasedCategorizer(await load_domain_rules(session, user_id))
    return categorizer.categorize(facts)


async def create_rule(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    data: RuleCreate,
    correlation_id: str | None = None,
) -> CategorizationRule:
    definition = _draft_to_domain(data)
    _validate_or_raise(definition)

    rule_id = data.id or new_id()
    existing = await repo.get(session, user_id, rule_id)
    if existing is not None:
        return existing

    rule = CategorizationRule(
        id=rule_id,
        user_id=user_id,
        name=data.name,
        priority=data.priority,
        logic=data.logic,
        conditions=[c.model_dump(mode="json") for c in data.conditions],
        set_category_id=data.set_category_id,
        set_merchant_id=data.set_merchant_id,
        tags=list(data.tags),
        stop_processing=data.stop_processing,
        is_active=data.is_active,
        version=1,
        server_seq=await next_server_seq(session, user_id),
    )
    repo.add(session, rule)
    audit_record(
        session,
        user_id=user_id,
        action="create",
        entity_type="rule",
        entity_id=rule_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={"name": data.name, "priority": data.priority},
    )
    await session.flush()
    return rule


async def update_rule(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: RuleUpdate,
    correlation_id: str | None = None,
) -> CategorizationRule:
    rule = await repo.get(session, user_id, rule_id)
    if rule is None:
        raise NotFoundError("rule not found")

    fields = data.model_dump(exclude_unset=True)
    if "conditions" in fields and data.conditions is not None:
        fields["conditions"] = [c.model_dump(mode="json") for c in data.conditions]

    for key, value in fields.items():
        setattr(rule, key, value)

    _validate_or_raise(_rule_to_domain(rule))

    rule.version += 1
    rule.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="update",
        entity_type="rule",
        entity_id=rule_id,
        actor_id=user_id,
        correlation_id=correlation_id,
        diff={k: v for k, v in fields.items() if k != "conditions"},
    )
    await session.flush()
    return rule


async def delete_rule(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    rule_id: uuid.UUID,
    clock: Clock,
    correlation_id: str | None = None,
) -> None:
    rule = await repo.get(session, user_id, rule_id)
    if rule is None:
        raise NotFoundError("rule not found")
    rule.deleted_at = clock.now()
    rule.version += 1
    rule.server_seq = await next_server_seq(session, user_id)
    audit_record(
        session,
        user_id=user_id,
        action="delete",
        entity_type="rule",
        entity_id=rule_id,
        actor_id=user_id,
        correlation_id=correlation_id,
    )
    await session.flush()


def test_draft(data: RuleCreate, facts: TransactionFacts) -> bool:
    """Validate a draft rule and report whether it matches sample facts."""
    definition = _draft_to_domain(data)
    try:
        return check_rule(definition, facts)
    except RuleValidationError as exc:
        raise RuleInvalidError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class SimChange:
    transaction_id: uuid.UUID
    current_category_id: uuid.UUID | None
    proposed_category_id: uuid.UUID | None
    changed: bool


async def simulate(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    draft: RuleCreate | None,
    limit: int,
) -> tuple[int, list[SimChange]]:
    """Dry-run the active rules (optionally plus a draft) over recent transactions."""
    definitions = await load_domain_rules(session, user_id, active_only=True)
    if draft is not None:
        draft_def = _draft_to_domain(draft)
        _validate_or_raise(draft_def)
        definitions = [*definitions, draft_def]

    categorizer = RuleBasedCategorizer(definitions)
    fact_rows = await recent_facts(session, user_id, limit=limit)

    changes: list[SimChange] = []
    for row in fact_rows:
        result = categorizer.categorize(row.facts)
        proposed = result.category_id
        changed = proposed is not None and proposed != row.current_category_id
        changes.append(SimChange(row.transaction_id, row.current_category_id, proposed, changed))
    return len(fact_rows), changes
