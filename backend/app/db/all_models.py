"""Import every ORM model so `Base.metadata` is complete.

Imported by Alembic (autogenerate) and by tests that create the schema. Import this
module for its side effects; the names are re-exported for convenience.
"""

from __future__ import annotations

from app.db.sequence import SyncSequence
from app.events.outbox import OutboxEntry
from app.modules.accounts.models import Account
from app.modules.audit.models import AuditLog
from app.modules.budgets.models import Budget, BudgetAlert, BudgetCategoryAllocation
from app.modules.categories.models import Category
from app.modules.goals.models import Goal, GoalContribution, GoalMilestone
from app.modules.ledger.models import LedgerEntry, Transaction
from app.modules.merchants.models import Merchant
from app.modules.recurring.models import RecurringSeries
from app.modules.rules.models import CategorizationRule

__all__ = [
    "Account",
    "AuditLog",
    "Budget",
    "BudgetAlert",
    "BudgetCategoryAllocation",
    "CategorizationRule",
    "Category",
    "Goal",
    "GoalContribution",
    "GoalMilestone",
    "LedgerEntry",
    "Merchant",
    "OutboxEntry",
    "RecurringSeries",
    "SyncSequence",
    "Transaction",
]
