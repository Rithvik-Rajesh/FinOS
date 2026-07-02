# FinOS — API Design

REST over HTTPS, JSON, JWT-authenticated. The API serves an offline-first mobile client,
so it is designed around **idempotent writes** and a **delta sync protocol** in addition to
normal resource endpoints.

- Base URL: `https://api.<domain>/v1`
- Auth: `Authorization: Bearer <access_jwt>` (verified via Supabase JWKS)
- All writes accept `Idempotency-Key: <uuid>` and are safe to retry.
- All list endpoints are cursor-paginated and tenant-scoped server-side.

---

## Conventions

- **Resource IDs** are UUIDv7 supplied by the client on create (so offline creates get a
  stable id). The server rejects a duplicate id for the same user idempotently.
- **Money** is always `{ "amount_minor": 28000, "currency": "INR" }` — integers only.
- **Timestamps** are ISO-8601 UTC (`2026-07-03T10:15:00Z`).
- **Field naming** is `snake_case`.
- **Soft delete** via `DELETE` sets `deleted_at`; the row still returns in sync as a tombstone.

## Versioning strategy

- **URI versioning**: `/v1`. Simple, cache-friendly, unambiguous for a mobile client that
  may lag behind the server.
- **Additive within a version**: new optional fields and endpoints never break a version.
  Breaking changes → `/v2`, with `/v1` supported through a deprecation window.
- **Client compatibility header**: the app sends `X-Client-Version`; the server can return
  `426 Upgrade Required` if a client is below the minimum supported version (important for a
  financial app where we must be able to force-fix a bad client).
- **Deprecation signaling**: `Deprecation` and `Sunset` response headers on retiring
  endpoints.

## Authentication endpoints

Auth (sign-up, OTP, OAuth, refresh) is handled by **Supabase Auth SDK on the client**;
the FinOS API does not implement login. The API only:

```
GET  /v1/me                      -> current user profile (JIT-creates on first call)
PATCH/v1/me                      -> update preferences (base currency, locale, flags)
POST /v1/devices                 -> register a device for sync
DELETE /v1/devices/{id}          -> revoke a device
POST /v1/account/export          -> request data export (async, audited, re-auth)
POST /v1/account/delete          -> delete account & data (re-auth, audited)
```

## Core resource endpoints (representative)

```
# Ledger
GET    /v1/transactions?from=&to=&category_id=&merchant_id=&cursor=&limit=
POST   /v1/transactions
GET    /v1/transactions/{id}
PATCH  /v1/transactions/{id}
DELETE /v1/transactions/{id}

GET/POST/PATCH/DELETE  /v1/accounts
GET/POST/PATCH/DELETE  /v1/categories
GET/POST/PATCH/DELETE  /v1/merchants
GET/POST/PATCH/DELETE  /v1/rules            # categorization rules
POST   /v1/rules/preview                    # dry-run a rule over recent txns

# Budgets
GET/POST/PATCH/DELETE  /v1/budgets
GET    /v1/budgets/status?period=2026-07    # limit vs spent vs projected (computed)

# Goals
GET/POST/PATCH/DELETE  /v1/goals
POST   /v1/goals/{id}/contributions
GET    /v1/goals/{id}/projection            # required monthly, ETA (computed)

# Calendar / recurring / subscriptions
GET/POST/PATCH/DELETE  /v1/recurring-items
GET    /v1/calendar?from=&to=               # scheduled_instances in range
GET    /v1/cashflow/forecast?horizon_days=90
GET    /v1/subscriptions                    # recurring-items where is_subscription
GET    /v1/subscriptions/summary            # monthly + annual cost analysis (computed)

# Wealth
GET/POST/PATCH/DELETE  /v1/assets
POST   /v1/assets/{id}/snapshots
GET    /v1/wealth/net-worth                 # computed rollup + allocation

# Insights
GET    /v1/insights/growth?dimension=category&window=mom
GET    /v1/insights/weekly-review?week=2026-W27

# Simulator
POST   /v1/simulator/affordability          # "can I afford X?" -> deterministic impact

# Files
POST   /v1/attachments/presign              # -> presigned PUT url + object key
POST   /v1/attachments                      # register metadata after upload
GET    /v1/attachments/{id}/download        # -> short-lived presigned GET

# AI (optional, feature-flagged)
POST   /v1/ai/conversations
POST   /v1/ai/conversations/{id}/messages   # streamed response
```

## Request / response examples

### Create a transaction (offline-generated id, idempotent)

```http
POST /v1/transactions
Authorization: Bearer <jwt>
Idempotency-Key: 018f9c2a-...-key
Content-Type: application/json

{
  "id": "018f9c1e-3b7a-7c2d-9f10-2a...",
  "account_id": "018f9b00-...",
  "type": "expense",
  "amount": { "amount_minor": 28000, "currency": "INR" },
  "occurred_at": "2026-07-03T13:45:00Z",
  "merchant_id": "018f9a55-...",     // Swiggy
  "category_id": null,                // let rules decide server-side
  "note": "dinner",
  "source": "manual"
}
```

```http
201 Created
{
  "id": "018f9c1e-3b7a-7c2d-9f10-2a...",
  "type": "expense",
  "amount": { "amount_minor": 28000, "currency": "INR" },
  "occurred_at": "2026-07-03T13:45:00Z",
  "category_id": "018f9a01-...",      // assigned by rule
  "merchant_id": "018f9a55-...",
  "rule_id": "018f9a77-...",
  "server_seq": 4821,
  "created_at": "2026-07-03T13:45:02Z",
  "updated_at": "2026-07-03T13:45:02Z",
  "deleted_at": null,
  "version": 1
}
```

### Affordability simulation (deterministic)

```http
POST /v1/simulator/affordability
{
  "purchase": { "amount_minor": 9500000, "currency": "INR" },  // ₹95,000 laptop
  "funding": "savings",           // savings | emi | goal_pause
  "emi_months": null
}
```

```http
200 OK
{
  "verdict": "affordable_with_impact",
  "cashflow": {
    "this_month_surplus_before": { "amount_minor": 4200000, "currency": "INR" },
    "this_month_surplus_after":  { "amount_minor": -5300000, "currency": "INR" }
  },
  "savings_rate": { "before_pct": 32.0, "after_pct": -8.0 },
  "emergency_fund": { "months_runway_before": 5.4, "months_runway_after": 3.1 },
  "goal_impact": [
    { "goal_id": "...", "name": "Masters Abroad", "delay_months": 2 }
  ],
  "computed_by": "deterministic-engine",   // never an LLM
  "explanation_available": true            // AI narration can be requested separately
}
```

Note: the **numbers are computed deterministically**; a natural-language explanation is a
separate, optional `POST /v1/ai/...` call that consumes exactly these figures.

## Sync protocol

The client keeps a full local DB and reconciles via a two-way delta.

### Pull (server → client)

```http
GET /v1/sync?since=4800&limit=500
```

```http
200 OK
{
  "changes": {
    "transactions": [ { ...row..., "server_seq": 4821, "deleted_at": null }, ... ],
    "goals":        [ ... ],
    "recurring_items": [ ... ]
  },
  "next_cursor": 4990,
  "has_more": false
}
```

The client applies rows where `server_seq > since`, folds server-normalized fields
(category assigned by rules, computed flags), and advances its cursor. Tombstones
(`deleted_at != null`) delete locally.

### Push (client → server)

```http
POST /v1/sync
Idempotency-Key: <uuid>
{
  "mutations": [
    { "op": "upsert", "entity": "transactions", "data": { "id": "...", ... }, "base_version": 1 },
    { "op": "delete", "entity": "goals", "id": "...", "base_version": 3 }
  ]
}
```

```http
200 OK
{
  "results": [
    { "id": "...", "status": "applied",  "server_seq": 4991, "server_row": { ... } },
    { "id": "...", "status": "conflict", "server_seq": 4890, "server_row": { ... },
      "resolution": "server_wins" }
  ],
  "next_cursor": 4991
}
```

**Conflict handling:** last-writer-wins by server `updated_at`; append-only entities prefer
insert; `base_version` mismatch surfaces a `conflict` with the authoritative `server_row`
so the client can reconcile. Policy is centralized server-side and upgradeable to
field-level merge (see [ADR-006](../ARCHITECTURE.md#adr-006--sync-client-uuids-outbox-delta-lww)).

## Error handling strategy

Consistent envelope, stable machine-readable `code`, human `message`, and a
`correlation_id` for support/debugging. **Never leak stack traces or internals.**

```http
422 Unprocessable Entity
{
  "error": {
    "code": "validation_error",
    "message": "amount_minor must be a positive integer",
    "details": [ { "field": "amount.amount_minor", "issue": "must be > 0" } ],
    "correlation_id": "req_018f9c...",
    "doc_url": "https://docs.<domain>/errors/validation_error"
  }
}
```

| HTTP | `code` examples | Meaning |
|---|---|---|
| 400 | `bad_request` | Malformed request. |
| 401 | `unauthenticated` | Missing/invalid/expired JWT. |
| 403 | `forbidden` | Authenticated but not the owner / not allowed. |
| 404 | `not_found` | Absent or not owned (we return 404, not 403, to avoid leaking existence). |
| 409 | `conflict`, `idempotency_conflict` | Sync/version conflict; reused idempotency key with a different body. |
| 422 | `validation_error` | Schema/business-rule validation failed. |
| 426 | `client_upgrade_required` | Client below minimum supported version. |
| 429 | `rate_limited` | Includes `Retry-After`; distinct code for `ai_budget_exceeded`. |
| 5xx | `internal_error` | Generic; details only in server logs under the correlation id. |

**Principles:** validate at the edge (Pydantic), fail closed, return the same shape
everywhere, make errors idempotency- and retry-friendly, and give the client enough to act
(e.g. `Retry-After`, `server_row` on conflict) without exposing internals.
