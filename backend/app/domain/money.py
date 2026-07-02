"""The Money value type.

All monetary amounts in FinOS are integer **minor units** (e.g. paise for INR) plus a
currency code. This eliminates floating-point rounding drift and makes multi-currency a
data concern rather than a rewrite (ADR-004).

Never represent money as a float. Construct from major units only via `Money.of()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal

# Minor units per major unit. INR/USD/EUR use 2; extend as we add zero-decimal
# currencies (e.g. JPY = 0). Kept explicit so rounding is never guessed.
_MINOR_UNITS: dict[str, int] = {
    "INR": 2,
    "USD": 2,
    "EUR": 2,
}
_DEFAULT_EXPONENT = 2


def minor_unit_exponent(currency: str) -> int:
    return _MINOR_UNITS.get(currency.upper(), _DEFAULT_EXPONENT)


class CurrencyMismatchError(ValueError):
    """Raised when two Money values of different currencies are combined."""


@dataclass(frozen=True, slots=True)
class Money:
    """An immutable amount of money in integer minor units."""

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if not isinstance(self.amount_minor, int) or isinstance(self.amount_minor, bool):
            raise TypeError("amount_minor must be an int (minor units), never a float")
        if len(self.currency) != 3 or not self.currency.isalpha():
            raise ValueError(f"currency must be a 3-letter code, got {self.currency!r}")
        # Normalize currency to upper-case without mutating a frozen dataclass.
        object.__setattr__(self, "currency", self.currency.upper())

    # ---- Constructors ----
    @classmethod
    def zero(cls, currency: str) -> Money:
        return cls(0, currency)

    @classmethod
    def of(cls, major: str | int | Decimal, currency: str) -> Money:
        """Build from a MAJOR-unit value (e.g. "95000.50" INR -> 9500050 paise).

        Accepts str/int/Decimal — deliberately NOT float, to avoid binary rounding.
        """
        exponent = minor_unit_exponent(currency)
        quantum = Decimal(1).scaleb(-exponent)
        value = Decimal(major).quantize(quantum, rounding=ROUND_HALF_EVEN)
        return cls(int(value.scaleb(exponent)), currency)

    # ---- Arithmetic (currency-safe) ----
    def _check(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"cannot combine {self.currency} with {other.currency}")

    def __add__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_minor + other.amount_minor, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._check(other)
        return Money(self.amount_minor - other.amount_minor, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount_minor, self.currency)

    def scale(self, factor: int) -> Money:
        """Multiply by an integer factor (e.g. 12 monthly -> annual). Stays exact."""
        return Money(self.amount_minor * factor, self.currency)

    # ---- Predicates ----
    @property
    def is_zero(self) -> bool:
        return self.amount_minor == 0

    @property
    def is_negative(self) -> bool:
        return self.amount_minor < 0

    def __lt__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor < other.amount_minor

    def __le__(self, other: Money) -> bool:
        self._check(other)
        return self.amount_minor <= other.amount_minor

    # ---- Presentation helpers ----
    @property
    def major(self) -> Decimal:
        """Exact decimal in major units (for display/serialization only)."""
        return Decimal(self.amount_minor).scaleb(-minor_unit_exponent(self.currency))

    def __str__(self) -> str:
        return f"{self.major} {self.currency}"


def sum_money(items: list[Money], currency: str) -> Money:
    """Sum a list of same-currency Money, starting from zero of `currency`."""
    total = Money.zero(currency)
    for item in items:
        total = total + item
    return total
