# FinOS — Sync Architecture

FinOS is offline-first: the mobile app owns a full local database and works with no
network; the server is the authority for cross-device merge. This document defines the
sync-ready entity design, the delta protocol, conflict handling, and recovery.

Code: [`app/modules/sync/`](../backend/app/modules/sync),
[`app/db/sequence.py`](../backend/app/db/sequence.py).

```
Flutter (local DB) ──▶ outbox ──▶ POST /v1/sync (push)
        ▲                                  │
        └────────── GET /v1/sync (pull) ◀──┘   FastAPI ──▶ PostgreSQL
```

> Client DB note: the reference client uses **Drift/SQLite** (ADR-002); the protocol is
> client-agnostic and works identically with Isar or any local store. What matters is that
> the client keeps `server_seq`, `version`, and a mutation outbox.

---

## 1. Sync-ready entity design

Every syncable row carries (via `SyncMixin`):

| Column | Role |
|---|---|
| `id` (UUIDv7) | Client-generatable primary key — offline creates never collide. |
| `version` | Bumped on every server-applied change; used for conflict detection. |
| `server_seq` | Per-user monotonic cursor value; assigned on every write. |
| `deleted_at` | Soft delete / tombstone, so deletes propagate. |
| `updated_at` | Server timestamp; the tiebreaker for last-writer-wins. |

Syncable entities: **accounts, categories, merchants, rules, transactions**. Ledger
entries are *not* synced — the client re-derives balances from transactions, keeping the
protocol small.

## 2. The cursor: `server_seq`

Each user has a monotonic counter (`sync_sequence`). Every syncable write allocates the
next value under a row lock (`next_server_seq`). A client stores the highest `server_seq`
it has seen; the sequence is strictly increasing per user and gap-tolerant (ordering is
what matters, not contiguity).

## 3. Pull (server → client)

```
GET /v1/sync?since=<cursor>&limit=<n>
```

Returns every row (across all syncable entities) with `server_seq > since`, ordered by
`server_seq`, including tombstones. Each `SyncChange` is `{entity, id, server_seq,
version, deleted, data}` (`data` is null for tombstones). The response includes
`next_cursor` and `has_more`.

The client applies changes in order, folds server-normalized fields (e.g. a category
assigned by a rule), deletes tombstoned rows locally, and advances its cursor.

- **Incremental sync**: `since = last_cursor` → only what changed.
- **Full-sync recovery**: `since = 0` → the entire current dataset (a fresh install, a
  restored device, or a client that fell too far behind simply pulls from 0).

## 4. Push (client → server)

```
POST /v1/sync   { "mutations": [ {op, entity, id, base_version, data}, ... ] }
```

The client drains its outbox. Each mutation is `upsert` or `delete` with the
`base_version` the client last saw. The server:

1. Loads the current row (tenant-scoped).
2. **Conflict detection**: if the row exists and `existing.version != base_version`, it
   returns `status: "conflict"` with the authoritative `server_data` — no write occurs.
3. Otherwise applies the change through the owning module's service (so posting, rules,
   audit, and events all run), allocates a new `server_seq`, and returns `status:
   "applied"` with the server row.
4. Errors (validation) return `status: "error"` with a message; other mutations in the
   batch are unaffected.

Results are per-mutation, so a client reconciles conflicts individually.

## 5. Conflict resolution

- **Policy**: last-writer-wins by server `updated_at`, surfaced to the client as an
  explicit `conflict` (with the server row) whenever `base_version` is stale — the client
  decides whether to re-apply on top of the server state or discard.
- **Append-only bias**: transactions, and their ledger entries, prefer inserts over
  in-place edits, so genuine field-level conflicts are rare in practice (the common case
  is two devices adding different transactions, which never conflict).
- **Idempotency**: creates use client UUIDs and are idempotent; the transaction engine
  also has `external_ref` for idempotent ingestion. Replaying the outbox is always safe.
- The policy is centralized in one service and can be upgraded to field-level merge later
  without touching modules.

## 6. Ordering & correctness properties

- **No lost updates**: `version` gating turns a blind overwrite into a detectable conflict.
- **No lost deletes**: tombstones sync like any other change.
- **Total order per user**: `server_seq` gives a replayable order; a client that applies
  changes in `server_seq` order converges to server state.
- **At-least-once side effects**: server-side reactions go through the transactional
  outbox (see [EVENT_ARCHITECTURE.md](EVENT_ARCHITECTURE.md)); handlers are idempotent.

## 7. Failure & recovery scenarios

| Scenario | Handling |
|---|---|
| Offline for a long time | Outbox accumulates; push replays idempotently; pull from last cursor. |
| Lost/reset device | Full-sync recovery (`since=0`) rebuilds the local DB. |
| Partial push (network drop mid-batch) | Applied mutations are durable; unacked ones are re-pushed (idempotent). |
| Clock skew between devices | Ordering uses server `server_seq`/`updated_at`, not client clocks. |
| Duplicate submit | Same client UUID → idempotent no-op. |

## 8. Security

All sync endpoints are tenant-scoped server-side; a client can only pull/push its own
rows. Conflicts return the server row but never another user's data. See
[SECURITY_REVIEW.md](SECURITY_REVIEW.md).
