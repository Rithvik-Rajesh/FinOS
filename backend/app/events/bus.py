"""In-process event bus.

Modules subscribe handlers to event types; publishers emit events without knowing who
listens. This is for synchronous, same-process reactions. Cross-process/durable
delivery uses the `Outbox` instead (see `outbox.py`).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.domain.events import DomainEvent

log = get_logger(__name__)

EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBus:
    """A minimal async publish/subscribe bus keyed on event type."""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[DomainEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Invoke every handler registered for the event's concrete type.

        A failing handler is logged and isolated so it cannot break the publisher or
        sibling handlers; durable delivery is the Outbox's responsibility.
        """
        for handler in self._handlers.get(type(event), []):
            try:
                await handler(event)
            except Exception:  # noqa: BLE001 - isolate subscriber failures
                log.error("event_handler_failed", event_name=event.name, handler=repr(handler))


# A process-wide default bus. Modules register handlers at startup.
bus = EventBus()
