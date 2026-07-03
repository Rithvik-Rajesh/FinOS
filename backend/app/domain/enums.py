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


# --------------------------------------------------------------------------- #
# Financial planning layer
# --------------------------------------------------------------------------- #
class GoalType(StrEnum):
    SAVINGS = "savings"
    PURCHASE = "purchase"
    EMERGENCY_FUND = "emergency_fund"
    EDUCATION = "education"
    TRAVEL = "travel"
    CUSTOM = "custom"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    ACHIEVED = "achieved"
    ARCHIVED = "archived"


class GoalHealth(StrEnum):
    """Deterministic on-track assessment of a goal."""

    ON_TRACK = "on_track"
    AHEAD = "ahead"
    BEHIND_SCHEDULE = "behind_schedule"
    ACHIEVED = "achieved"
    NO_DEADLINE = "no_deadline"
    AT_RISK = "at_risk"  # deadline in the past, not achieved


class BudgetPeriodType(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class BudgetHealth(StrEnum):
    UNDER = "under"  # within allocation
    WARNING = "warning"  # crossed the warning threshold
    OVER = "over"  # overspent


class RecurrenceInterval(StrEnum):
    """How often a recurring series repeats."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class RecurringKind(StrEnum):
    RENT = "rent"
    EMI = "emi"
    SIP = "sip"
    UTILITY = "utility"
    SUBSCRIPTION = "subscription"
    SALARY = "salary"
    OTHER = "other"


class RecurringDirection(StrEnum):
    INFLOW = "inflow"  # income (salary)
    OUTFLOW = "outflow"  # expense (rent, subscription)


class RecurringStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"  # auto-detected, awaiting user confirmation
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class OccurrenceStatus(StrEnum):
    UPCOMING = "upcoming"
    PAID = "paid"
    SKIPPED = "skipped"
    MISSED = "missed"  # due date passed with no matching transaction


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class BillingCycle(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class FinancialEventType(StrEnum):
    BILL = "bill"
    SUBSCRIPTION = "subscription"
    EMI = "emi"
    GOAL_MILESTONE = "goal_milestone"
    BUDGET_CHECKPOINT = "budget_checkpoint"
    SALARY = "salary"
    RECURRING_EXPENSE = "recurring_expense"


class ForecastHorizon(StrEnum):
    D30 = "30d"
    D90 = "90d"
    D180 = "180d"
    Y1 = "1y"

    @property
    def days(self) -> int:
        return {"30d": 30, "90d": 90, "180d": 180, "1y": 365}[self.value]


# --------------------------------------------------------------------------- #
# Product experience layer
# --------------------------------------------------------------------------- #
class FinancialPriority(StrEnum):
    SAVINGS_FIRST = "savings_first"
    GOAL_FIRST = "goal_first"
    DEBT_REDUCTION_FIRST = "debt_reduction_first"
    BALANCED = "balanced"


class RiskProfile(StrEnum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class InsightCategory(StrEnum):
    SPENDING = "spending"
    GOAL = "goal"
    BUDGET = "budget"
    SUBSCRIPTION = "subscription"
    FORECAST = "forecast"


class InsightSeverity(StrEnum):
    POSITIVE = "positive"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReviewPeriod(StrEnum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class NotificationType(StrEnum):
    GOAL_REMINDER = "goal_reminder"
    BUDGET_WARNING = "budget_warning"
    SUBSCRIPTION_RENEWAL = "subscription_renewal"
    UPCOMING_BILL = "upcoming_bill"
    FORECAST_WARNING = "forecast_warning"
    GOAL_COMPLETION = "goal_completion"


class NotificationChannel(StrEnum):
    IN_APP = "in_app"
    PUSH = "push"
    EMAIL = "email"


class NotificationStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    READ = "read"
    DISMISSED = "dismissed"
