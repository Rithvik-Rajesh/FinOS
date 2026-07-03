"""Domain enumerations.

All string-valued so they serialize cleanly over JSON and store portably (as VARCHAR
with a check constraint) on any database. These are part of the domain vocabulary and
carry no infrastructure concerns.
"""

from __future__ import annotations

from enum import StrEnum


class TransactionType(StrEnum):
    """What a transaction represents.

    The posting rules for each type live in `app.domain.ledger`:

    * EXPENSE    — money leaves an account (single-sided, account decreases).
    * INCOME     — money enters an account (single-sided, account increases).
    * TRANSFER   — money moves between two tracked accounts (balanced, nets to zero).
    * REFUND     — money returns to an account, typically reversing an earlier expense.
    * ADJUSTMENT — a manual correction (reconciliation); amount may be signed.
    """

    EXPENSE = "expense"
    INCOME = "income"
    TRANSFER = "transfer"
    REFUND = "refund"
    ADJUSTMENT = "adjustment"


class TransactionStatus(StrEnum):
    """Reconciliation lifecycle of a transaction."""

    PENDING = "pending"  # recorded but not yet confirmed against a statement
    CLEARED = "cleared"  # confirmed to have settled
    RECONCILED = "reconciled"  # matched during an account reconciliation


class TransactionSource(StrEnum):
    """How the transaction entered the system (provenance for audit + trust)."""

    MANUAL = "manual"
    RULE = "rule"
    IMPORT = "import"
    RECURRING = "recurring"


class AccountType(StrEnum):
    """Kind of money container."""

    CASH = "cash"
    SAVINGS = "savings"
    CURRENT = "current"
    CREDIT_CARD = "credit_card"
    WALLET = "wallet"
    INVESTMENT = "investment"


class EntryDirection(StrEnum):
    """Direction of a ledger entry relative to the account's own balance."""

    INFLOW = "inflow"  # increases the account balance (signed amount > 0)
    OUTFLOW = "outflow"  # decreases the account balance (signed amount < 0)


class CategorizationSource(StrEnum):
    """Where a category assignment came from.

    Designed so a future ML categorizer plugs in as another source without changing
    the transaction model (see EVENT_ARCHITECTURE.md / TRANSACTION_ENGINE.md).
    """

    MANUAL = "manual"
    USER_RULE = "user_rule"
    ML_MODEL = "ml_model"
    DEFAULT = "default"


class RuleField(StrEnum):
    """Fields a categorization rule may test."""

    MERCHANT = "merchant"
    COUNTERPARTY = "counterparty"
    ACCOUNT = "account"
    TYPE = "type"
    AMOUNT = "amount"  # tested in minor units
    NOTE = "note"
    HOUR_OF_DAY = "hour_of_day"  # 0-23, in the user's timezone
    DAY_OF_WEEK = "day_of_week"  # 0=Monday .. 6=Sunday


class RuleOperator(StrEnum):
    """Comparison operators available to rule predicates."""

    EQ = "eq"
    NE = "ne"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    CONTAINS = "contains"  # case-insensitive substring, for text fields
    IN = "in"  # value is a list; field must be a member
    BETWEEN = "between"  # value is [low, high]; inclusive


class RuleLogic(StrEnum):
    """How a rule's predicates combine."""

    ALL = "all"  # every predicate must match (AND)
    ANY = "any"  # at least one predicate must match (OR)


class Period(StrEnum):
    """Reporting period granularity."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"
