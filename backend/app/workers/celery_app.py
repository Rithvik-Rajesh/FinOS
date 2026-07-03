"""Celery application.

Async work — recurring-item materialization, upcoming-bill notifications, period
rollups, weekly reviews, insight precompute (docs ARCHITECTURE.md#8-event-flow). Tasks
land alongside their modules from Phase 3 on. This wires the app + broker now.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("finos", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,  # at-least-once; handlers must be idempotent
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="finos.ping")  # type: ignore[untyped-decorator]  # celery is untyped
def ping() -> str:
    """Trivial task to verify broker connectivity."""
    return "pong"
