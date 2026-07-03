"""Sync protocol schemas (see SYNC_ARCHITECTURE.md)."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

SyncEntity = Literal[
    "accounts",
    "categories",
    "merchants",
    "rules",
    "transactions",
    "goals",
    "budgets",
    "recurring",
    "profiles",
]


class SyncChange(BaseModel):
    """One changed row in a pull response (or a tombstone when deleted=True)."""

    entity: SyncEntity
    id: uuid.UUID
    server_seq: int
    version: int
    deleted: bool
    data: dict[str, Any] | None  # null for tombstones


class SyncPullResponse(BaseModel):
    changes: list[SyncChange]
    next_cursor: int
    has_more: bool


class SyncMutation(BaseModel):
    op: Literal["upsert", "delete"]
    entity: SyncEntity
    id: uuid.UUID
    base_version: int | None = None  # None for first create; used for conflict detection
    data: dict[str, Any] | None = None


class SyncPushRequest(BaseModel):
    mutations: list[SyncMutation] = Field(default_factory=list)


class SyncMutationResult(BaseModel):
    id: uuid.UUID
    entity: SyncEntity
    status: Literal["applied", "conflict", "error"]
    server_seq: int | None = None
    version: int | None = None
    server_data: dict[str, Any] | None = None  # authoritative row on conflict
    message: str | None = None


class SyncPushResponse(BaseModel):
    results: list[SyncMutationResult]
    next_cursor: int
