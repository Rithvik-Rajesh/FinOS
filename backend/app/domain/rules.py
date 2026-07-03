"""The categorization rules engine — pure and deterministic.

A rule is a set of predicates (combined with ALL/ANY) plus the actions to take when it
matches (assign a category and/or merchant). Rules are evaluated in ascending priority
order; the first match for a given action wins, and a rule may stop further processing.

Extensibility for ML: categorization is expressed through the `Categorizer` protocol.
`RuleBasedCategorizer` is one implementation; a future ML model implements the same
protocol and is composed via `CompositeCategorizer`, so the transaction pipeline never
needs to know which produced a result (see EVENT_ARCHITECTURE.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.domain.enums import (
    CategorizationSource,
    RuleField,
    RuleLogic,
    RuleOperator,
    TransactionType,
)

RuleValue = str | int | bool | list[str] | list[int]

_TEXT_FIELDS = frozenset(
    {RuleField.MERCHANT, RuleField.COUNTERPARTY, RuleField.ACCOUNT, RuleField.NOTE, RuleField.TYPE}
)
_NUMERIC_FIELDS = frozenset({RuleField.AMOUNT, RuleField.HOUR_OF_DAY, RuleField.DAY_OF_WEEK})
_TEXT_OPERATORS = frozenset(
    {RuleOperator.EQ, RuleOperator.NE, RuleOperator.CONTAINS, RuleOperator.IN}
)
_NUMERIC_OPERATORS = frozenset(
    {
        RuleOperator.EQ,
        RuleOperator.NE,
        RuleOperator.GT,
        RuleOperator.GTE,
        RuleOperator.LT,
        RuleOperator.LTE,
        RuleOperator.IN,
        RuleOperator.BETWEEN,
    }
)


class RuleValidationError(ValueError):
    """Raised when a rule/predicate is structurally invalid."""


@dataclass(frozen=True, slots=True)
class TransactionFacts:
    """The pure facts a rule evaluates against.

    Absent facts (None) never match a predicate — a rule cannot fire on data it does
    not have. `hour_of_day` / `day_of_week` are computed in the user's timezone by the
    caller so evaluation stays pure.
    """

    type: TransactionType
    amount_minor: int
    currency: str
    hour_of_day: int
    day_of_week: int
    merchant_name: str | None = None
    counterparty: str | None = None
    account_name: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Predicate:
    field: RuleField
    operator: RuleOperator
    value: RuleValue


@dataclass(frozen=True, slots=True)
class RuleDefinition:
    """A pure, immutable rule as evaluated by the engine."""

    id: uuid.UUID
    priority: int
    predicates: tuple[Predicate, ...]
    logic: RuleLogic = RuleLogic.ALL
    set_category_id: uuid.UUID | None = None
    set_merchant_id: uuid.UUID | None = None
    tags: tuple[str, ...] = ()
    stop_processing: bool = False
    is_active: bool = True


@dataclass(frozen=True, slots=True)
class CategorizationResult:
    """The outcome of categorizing one transaction."""

    category_id: uuid.UUID | None = None
    merchant_id: uuid.UUID | None = None
    tags: tuple[str, ...] = ()
    matched_rule_ids: tuple[uuid.UUID, ...] = ()
    source: CategorizationSource = CategorizationSource.DEFAULT


class Categorizer(Protocol):
    """Anything that can categorize a transaction from its facts."""

    def categorize(self, facts: TransactionFacts) -> CategorizationResult: ...


# --------------------------------------------------------------------------- #
# Predicate evaluation
# --------------------------------------------------------------------------- #
def validate_predicate(predicate: Predicate) -> None:
    """Raise `RuleValidationError` if a predicate is structurally invalid."""
    fld, op, val = predicate.field, predicate.operator, predicate.value

    if fld in _TEXT_FIELDS and op not in _TEXT_OPERATORS:
        raise RuleValidationError(f"operator {op} is not valid for text field {fld}")
    if fld in _NUMERIC_FIELDS and op not in _NUMERIC_OPERATORS:
        raise RuleValidationError(f"operator {op} is not valid for numeric field {fld}")

    if op is RuleOperator.BETWEEN:
        if not (isinstance(val, list) and len(val) == 2 and all(isinstance(v, int) for v in val)):
            raise RuleValidationError("between requires a list of two integers")
    elif op is RuleOperator.IN:
        if not (isinstance(val, list) and len(val) > 0):
            raise RuleValidationError("in requires a non-empty list")
    elif isinstance(val, list):
        raise RuleValidationError(f"operator {op} does not take a list value")
    elif fld in _NUMERIC_FIELDS and not isinstance(val, int):
        raise RuleValidationError(f"numeric field {fld} requires an integer value")


def validate_rule(rule: RuleDefinition) -> None:
    """Raise `RuleValidationError` if a rule is structurally invalid."""
    if not rule.predicates:
        raise RuleValidationError("a rule must have at least one predicate")
    if rule.set_category_id is None and rule.set_merchant_id is None and not rule.tags:
        raise RuleValidationError("a rule must set a category, merchant, or tag")
    for predicate in rule.predicates:
        validate_predicate(predicate)


def _fact_for(field_: RuleField, facts: TransactionFacts) -> str | int | None:
    match field_:
        case RuleField.MERCHANT:
            return facts.merchant_name
        case RuleField.COUNTERPARTY:
            return facts.counterparty
        case RuleField.ACCOUNT:
            return facts.account_name
        case RuleField.NOTE:
            return facts.note
        case RuleField.TYPE:
            return facts.type.value
        case RuleField.AMOUNT:
            return facts.amount_minor
        case RuleField.HOUR_OF_DAY:
            return facts.hour_of_day
        case RuleField.DAY_OF_WEEK:
            return facts.day_of_week


def _eval_text(op: RuleOperator, actual: str, value: RuleValue) -> bool:
    a = actual.casefold()
    match op:
        case RuleOperator.EQ:
            return isinstance(value, str) and a == value.casefold()
        case RuleOperator.NE:
            return isinstance(value, str) and a != value.casefold()
        case RuleOperator.CONTAINS:
            return isinstance(value, str) and value.casefold() in a
        case RuleOperator.IN:
            return isinstance(value, list) and a in {str(v).casefold() for v in value}
        case _:
            return False


def _eval_numeric(op: RuleOperator, actual: int, value: RuleValue) -> bool:
    match op:
        case RuleOperator.EQ:
            return isinstance(value, int) and actual == value
        case RuleOperator.NE:
            return isinstance(value, int) and actual != value
        case RuleOperator.GT:
            return isinstance(value, int) and actual > value
        case RuleOperator.GTE:
            return isinstance(value, int) and actual >= value
        case RuleOperator.LT:
            return isinstance(value, int) and actual < value
        case RuleOperator.LTE:
            return isinstance(value, int) and actual <= value
        case RuleOperator.IN:
            return isinstance(value, list) and actual in {int(v) for v in value}
        case RuleOperator.BETWEEN:
            return (
                isinstance(value, list)
                and len(value) == 2
                and int(value[0]) <= actual <= int(value[1])
            )
        case _:
            return False


def evaluate_predicate(predicate: Predicate, facts: TransactionFacts) -> bool:
    actual = _fact_for(predicate.field, facts)
    if actual is None:
        return False
    if predicate.field in _TEXT_FIELDS:
        return _eval_text(predicate.operator, str(actual), predicate.value)
    return _eval_numeric(predicate.operator, int(actual), predicate.value)


def rule_matches(rule: RuleDefinition, facts: TransactionFacts) -> bool:
    """True if the rule (respecting its ALL/ANY logic) matches the facts."""
    if not rule.is_active or not rule.predicates:
        return False
    results = (evaluate_predicate(p, facts) for p in rule.predicates)
    return all(results) if rule.logic is RuleLogic.ALL else any(results)


# --------------------------------------------------------------------------- #
# Categorizers
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RuleBasedCategorizer:
    """Applies user rules in priority order.

    The first matching rule that provides an action wins for that action; a matching
    rule with `stop_processing` halts evaluation.
    """

    rules: Sequence[RuleDefinition]
    source: CategorizationSource = CategorizationSource.USER_RULE

    def categorize(self, facts: TransactionFacts) -> CategorizationResult:
        category_id: uuid.UUID | None = None
        merchant_id: uuid.UUID | None = None
        tags: list[str] = []
        matched: list[uuid.UUID] = []

        for rule in sorted(self.rules, key=lambda r: r.priority):
            if not rule_matches(rule, facts):
                continue
            matched.append(rule.id)
            if category_id is None and rule.set_category_id is not None:
                category_id = rule.set_category_id
            if merchant_id is None and rule.set_merchant_id is not None:
                merchant_id = rule.set_merchant_id
            for tag in rule.tags:
                if tag not in tags:
                    tags.append(tag)
            if rule.stop_processing:
                break

        source = self.source if matched else CategorizationSource.DEFAULT
        return CategorizationResult(
            category_id=category_id,
            merchant_id=merchant_id,
            tags=tuple(tags),
            matched_rule_ids=tuple(matched),
            source=source,
        )


@dataclass(frozen=True, slots=True)
class CompositeCategorizer:
    """Tries each categorizer in order, filling in only what earlier ones left unset.

    This is the seam for ML-assisted categorization: register a rule-based categorizer
    first and an ML categorizer as a fallback. Neither knows about the other.
    """

    categorizers: Sequence[Categorizer]

    def categorize(self, facts: TransactionFacts) -> CategorizationResult:
        category_id: uuid.UUID | None = None
        merchant_id: uuid.UUID | None = None
        tags: list[str] = []
        matched: list[uuid.UUID] = []
        source = CategorizationSource.DEFAULT

        for categorizer in self.categorizers:
            result = categorizer.categorize(facts)
            if category_id is None and result.category_id is not None:
                category_id = result.category_id
                source = result.source
            if merchant_id is None and result.merchant_id is not None:
                merchant_id = result.merchant_id
            for tag in result.tags:
                if tag not in tags:
                    tags.append(tag)
            matched.extend(result.matched_rule_ids)

        return CategorizationResult(
            category_id=category_id,
            merchant_id=merchant_id,
            tags=tuple(tags),
            matched_rule_ids=tuple(matched),
            source=source,
        )


# --------------------------------------------------------------------------- #
# Simulation & testing helpers (used by the rules API)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SimulatedAssignment:
    """The result of simulating rules against one historical transaction."""

    facts: TransactionFacts
    result: CategorizationResult


def simulate(
    rules: Sequence[RuleDefinition], facts_list: Sequence[TransactionFacts]
) -> list[SimulatedAssignment]:
    """Dry-run rules over a set of facts without mutating anything.

    Powers "what would this rule set do to my existing transactions?".
    """
    categorizer = RuleBasedCategorizer(rules)
    return [SimulatedAssignment(f, categorizer.categorize(f)) for f in facts_list]


def check_rule(rule: RuleDefinition, facts: TransactionFacts) -> bool:
    """Validate a single rule and report whether it matches the given facts.

    Powers the rules API's "test this rule against a sample transaction" endpoint.
    (Named `check_` rather than `test_` so it is never mistaken for a pytest case.)
    """
    validate_rule(rule)
    return rule_matches(rule, facts)


__all__ = [
    "Categorizer",
    "CategorizationResult",
    "CompositeCategorizer",
    "Predicate",
    "RuleBasedCategorizer",
    "RuleDefinition",
    "RuleValidationError",
    "SimulatedAssignment",
    "TransactionFacts",
    "check_rule",
    "evaluate_predicate",
    "rule_matches",
    "simulate",
    "validate_predicate",
    "validate_rule",
]
