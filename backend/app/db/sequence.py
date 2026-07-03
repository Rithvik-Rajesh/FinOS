"""Per-user monotonic sequence — the source of the sync cursor.

Every syncable write is stamped with a `server_seq` drawn from a per-user counter. A
client pulls everything with `server_seq > its_cursor`, so the sequence must be strictly
increasing per user and gap-tolerant (gaps are fine; ordering is what matters).
"""

from __future__ import annotations

import uuid

from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SyncSequence(Base):
    __tablename__ = "sync_sequence"

    user_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    next_seq: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)


async def next_server_seq(session: AsyncSession, user_id: uuid.UUID) -> int:
    """Allocate the next `server_seq` for a user within the caller's transaction.

    Uses a row lock (``FOR UPDATE`` on PostgreSQL; a no-op on SQLite, which already
    serializes writers) so concurrent writers cannot hand out the same number.
    """
    row = await session.get(SyncSequence, user_id, with_for_update=True)
    if row is None:
        session.add(SyncSequence(user_id=user_id, next_seq=2))
        return 1
    seq = row.next_seq
    row.next_seq = seq + 1
    return seq
