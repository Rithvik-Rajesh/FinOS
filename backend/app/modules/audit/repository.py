"""Writing to the audit log."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ids import new_id
from app.modules.audit.models import AuditLog


def record(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID,
    actor_id: uuid.UUID | None = None,
    actor_type: str = "user",
    diff: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    """Append an audit row within the caller's transaction (no commit)."""
    session.add(
        AuditLog(
            id=new_id(),
            user_id=user_id,
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            diff=diff,
            correlation_id=correlation_id,
        )
    )
