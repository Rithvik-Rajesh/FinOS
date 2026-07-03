"""Review calculations — the deterministic pieces of periodic reviews.

A review is a snapshot assembled from the other engines (spending, growth, goals, budgets,
subscriptions). The genuinely computed bit — the savings rate — lives here as pure,
tested arithmetic. See REVIEW_ENGINE.md.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.money import Money


def savings_rate(*, income: Money, spending: Money) -> Decimal | None:
    """(income − spending) / income, as a percentage rounded to one place.

    None when there is no income to measure against (avoids divide-by-zero).
    """
    if income.currency != spending.currency:
        from app.domain.money import CurrencyMismatchError

        raise CurrencyMismatchError("income and spending must share a currency")
    if income.amount_minor <= 0:
        return None
    saved = income.amount_minor - spending.amount_minor
    return (Decimal(saved) / Decimal(income.amount_minor) * Decimal(100)).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
