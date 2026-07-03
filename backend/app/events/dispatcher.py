"""Outbox dispatcher — drains the transactional outbox to registered handlers.

This is the integration seam for the planning layer: modules register idempotent handlers
keyed by event name, and a worker (or a test) calls `dispatch_pending`. The ledger never
knows who consumes its events (EVENT_ARCHITECTURE.md). Delivery is at-least-once, so
handlers must be idempotent.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.clock import Clock
from app.events.outbox import OutboxEntry

log = get_logger(__name__)

Handler = Callable[[AsyncSession, dict[str, Any], Clock], Awaitable[None]]


class Dispatcher:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def register(self, event_name: str, handler: Handler) -> None:
        self._handlers[event_name].append(handler)

    async def dispatch_pending(
        self, session: AsyncSession, *, clock: Clock, limit: int = 200
    ) -> int:
        """Process unpublished outbox rows in order. Returns how many were processed."""
        stmt = (
            select(OutboxEntry)
            .where(OutboxEntry.published_at.is_(None))
            .order_by(OutboxEntry.created_at)
            .limit(limit)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        for entry in rows:
            for handler in self._handlers.get(entry.event_name, []):
                try:
                    await handler(session, entry.payload, clock)
                except Exception:  # noqa: BLE001 - isolate handler failures
                    log.error(
                        "dispatch_handler_failed", event_name=entry.event_name, entry=str(entry.id)
                    )
            entry.published_at = clock.now()
        await session.flush()
        return len(rows)


dispatcher = Dispatcher()
