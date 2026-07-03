"""Event publishing infrastructure.

Domain event *types* live in `app.domain.events` (pure). This package holds the
*mechanism*: an in-process `EventBus` for synchronous in-request subscribers and a
transactional `Outbox` for reliable, at-least-once delivery to async consumers
(Celery). See EVENT_ARCHITECTURE.md.
"""
