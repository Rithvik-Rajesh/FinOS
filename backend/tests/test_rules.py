"""Tests for the categorization rules engine."""

from __future__ import annotations

import uuid

import pytest

from app.domain.enums import (
    CategorizationSource,
    RuleField,
    RuleLogic,
    RuleOperator,
    TransactionType,
)
from app.domain.rules import (
    CompositeCategorizer,
    Predicate,
    RuleBasedCategorizer,
    RuleDefinition,
    RuleValidationError,
    TransactionFacts,
    check_rule,
    simulate,
    validate_rule,
)

FOOD = uuid.uuid4()
FAMILY = uuid.uuid4()
LARGE = uuid.uuid4()


def _facts(**kwargs: object) -> TransactionFacts:
    base: dict[str, object] = {
        "type": TransactionType.EXPENSE,
        "amount_minor": 28000,
        "currency": "INR",
        "hour_of_day": 13,
        "day_of_week": 2,
    }
    base.update(kwargs)
    return TransactionFacts(**base)  # type: ignore[arg-type]


def _rule(pid: uuid.UUID, priority: int, predicate: Predicate, **kw: object) -> RuleDefinition:
    return RuleDefinition(id=pid, priority=priority, predicates=(predicate,), **kw)  # type: ignore[arg-type]


def test_merchant_swiggy_to_food() -> None:
    rule = _rule(
        uuid.uuid4(),
        10,
        Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
        set_category_id=FOOD,
    )
    result = RuleBasedCategorizer([rule]).categorize(_facts(merchant_name="swiggy"))
    assert result.category_id == FOOD
    assert result.source is CategorizationSource.USER_RULE


def test_recipient_mom_to_family() -> None:
    rule = _rule(
        uuid.uuid4(),
        10,
        Predicate(RuleField.COUNTERPARTY, RuleOperator.EQ, "Mom"),
        set_category_id=FAMILY,
    )
    result = RuleBasedCategorizer([rule]).categorize(_facts(counterparty="Mom"))
    assert result.category_id == FAMILY


def test_amount_over_threshold_is_large_purchase() -> None:
    rule = _rule(
        uuid.uuid4(),
        10,
        Predicate(RuleField.AMOUNT, RuleOperator.GT, 10000 * 100),  # ₹10,000 in paise
        set_category_id=LARGE,
    )
    matched = RuleBasedCategorizer([rule]).categorize(_facts(amount_minor=95000 * 100))
    missed = RuleBasedCategorizer([rule]).categorize(_facts(amount_minor=500 * 100))
    assert matched.category_id == LARGE
    assert missed.category_id is None


def test_priority_first_match_wins() -> None:
    high = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.MERCHANT, RuleOperator.CONTAINS, "swig"),
        set_category_id=FOOD,
    )
    low = _rule(
        uuid.uuid4(),
        5,
        Predicate(RuleField.MERCHANT, RuleOperator.CONTAINS, "swig"),
        set_category_id=FAMILY,
    )
    result = RuleBasedCategorizer([low, high]).categorize(_facts(merchant_name="Swiggy"))
    assert result.category_id == FOOD  # priority 1 wins over 5


def test_stop_processing_halts_evaluation() -> None:
    first = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.TYPE, RuleOperator.EQ, "expense"),
        set_merchant_id=None,
        tags=("reviewed",),
        stop_processing=True,
    )
    second = _rule(
        uuid.uuid4(),
        2,
        Predicate(RuleField.TYPE, RuleOperator.EQ, "expense"),
        set_category_id=FOOD,
    )
    result = RuleBasedCategorizer([first, second]).categorize(_facts())
    assert result.category_id is None  # second never ran
    assert result.tags == ("reviewed",)


def test_all_logic_requires_every_predicate() -> None:
    rule = RuleDefinition(
        id=uuid.uuid4(),
        priority=1,
        logic=RuleLogic.ALL,
        predicates=(
            Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
            Predicate(RuleField.AMOUNT, RuleOperator.GT, 10000),
        ),
        set_category_id=FOOD,
    )
    assert (
        RuleBasedCategorizer([rule])
        .categorize(_facts(merchant_name="Swiggy", amount_minor=50000))
        .category_id
        == FOOD
    )
    assert (
        RuleBasedCategorizer([rule])
        .categorize(_facts(merchant_name="Swiggy", amount_minor=100))
        .category_id
        is None
    )


def test_any_logic_requires_one_predicate() -> None:
    rule = RuleDefinition(
        id=uuid.uuid4(),
        priority=1,
        logic=RuleLogic.ANY,
        predicates=(
            Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Zomato"),
            Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
        ),
        set_category_id=FOOD,
    )
    assert (
        RuleBasedCategorizer([rule]).categorize(_facts(merchant_name="Swiggy")).category_id == FOOD
    )


def test_between_and_in_operators() -> None:
    between = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.HOUR_OF_DAY, RuleOperator.BETWEEN, [22, 23]),
        set_category_id=FOOD,
    )
    assert check_rule(between, _facts(hour_of_day=22))
    assert not check_rule(between, _facts(hour_of_day=10))

    in_rule = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.DAY_OF_WEEK, RuleOperator.IN, [5, 6]),
        set_category_id=FOOD,
    )
    assert check_rule(in_rule, _facts(day_of_week=6))
    assert not check_rule(in_rule, _facts(day_of_week=2))


def test_missing_fact_never_matches() -> None:
    rule = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
        set_category_id=FOOD,
    )
    assert not check_rule(rule, _facts(merchant_name=None))


def test_validation_rejects_bad_operator_for_field() -> None:
    rule = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.AMOUNT, RuleOperator.CONTAINS, "x"),
        set_category_id=FOOD,
    )
    with pytest.raises(RuleValidationError):
        validate_rule(rule)


def test_validation_requires_an_action() -> None:
    rule = RuleDefinition(
        id=uuid.uuid4(),
        priority=1,
        predicates=(Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),),
    )
    with pytest.raises(RuleValidationError):
        validate_rule(rule)


def test_simulate_over_history() -> None:
    rule = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
        set_category_id=FOOD,
    )
    facts = [_facts(merchant_name="Swiggy"), _facts(merchant_name="Uber")]
    results = simulate([rule], facts)
    assert results[0].result.category_id == FOOD
    assert results[1].result.category_id is None


def test_composite_falls_back() -> None:
    rule = _rule(
        uuid.uuid4(),
        1,
        Predicate(RuleField.MERCHANT, RuleOperator.EQ, "Swiggy"),
        set_category_id=FOOD,
    )

    class _StubMl:
        def categorize(self, facts: TransactionFacts) -> object:
            from app.domain.rules import CategorizationResult

            return CategorizationResult(category_id=FAMILY, source=CategorizationSource.ML_MODEL)

    composite = CompositeCategorizer([RuleBasedCategorizer([rule]), _StubMl()])  # type: ignore[list-item]
    # Rule matches -> rule wins.
    assert composite.categorize(_facts(merchant_name="Swiggy")).category_id == FOOD
    # Rule misses -> ML fallback fills it in.
    fell_back = composite.categorize(_facts(merchant_name="Uber"))
    assert fell_back.category_id == FAMILY
    assert fell_back.source is CategorizationSource.ML_MODEL
