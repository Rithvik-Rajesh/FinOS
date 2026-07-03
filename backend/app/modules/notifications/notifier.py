"""Delivery abstraction — no vendor lock-in.

A `Notifier` delivers a queued `NotificationEvent` over some channel. In-app delivery is a
no-op (the queued row *is* the in-app notification the client reads). Push/email notifiers
implement the same protocol later (FCM/APNs/SES/etc.) without touching the queue or the
generators (see NOTIFICATION_ENGINE.md).
"""

from __future__ import annotations

from typing import Protocol

from app.modules.notifications.models import NotificationEvent


class Notifier(Protocol):
    async def deliver(self, event: NotificationEvent) -> None: ...


class InAppNotifier:
    """In-app delivery: the queued event is itself the notification. No external call."""

    async def deliver(self, event: NotificationEvent) -> None:
        return None
