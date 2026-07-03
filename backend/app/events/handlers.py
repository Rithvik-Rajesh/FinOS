"""Planning-layer event handlers, registered on the outbox dispatcher.

Handlers are idempotent (delivery is at-least-once). They react to ledger events for
side effects that must be captured at event time — currently budget-threshold alerts.
Read models (goal projections, budget status, calendar, forecasts) are computed on read
and therefore need no event handling; they are always current (ADR-011).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.clock import Clock
from app.events.dispatcher import Dispatcher, dispatcher
from app.modules.budgets import service as budgets_service


async def on_transaction_created(
    session: AsyncSession, payload: dict[str, Any], clock: Clock
) -> None:
    """Re-evaluate budget alerts for the affected category."""
    category_id = payload.get("category_id")
    if category_id is None:
        return
    await budgets_service.evaluate_alerts(
        session,
        user_id=uuid.UUID(payload["user_id"]),
        category_id=uuid.UUID(category_id),
        clock=clock,
    )


def register_all(target: Dispatcher | None = None) -> None:
    """Idempotently register planning handlers. Called at startup and in tests."""
    bus = target or dispatcher
    if getattr(register_all, "_registered", False) and target is None:
        return
    bus.register("TransactionCreated", on_transaction_created)
    if target is None:
        register_all._registered = True  # type: ignore[attr-defined]
