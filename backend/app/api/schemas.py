"""Shared API schema building blocks."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

from app.domain.money import Money

CurrencyStr = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]


class MoneySchema(BaseModel):
    """Wire representation of money — integer minor units plus a currency code."""

    amount_minor: int
    currency: CurrencyStr

    @classmethod
    def from_money(cls, money: Money) -> MoneySchema:
        return cls(amount_minor=money.amount_minor, currency=money.currency)

    def to_money(self) -> Money:
        return Money(self.amount_minor, self.currency)


class Page[T](BaseModel):
    """A cursor-paginated result page."""

    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
