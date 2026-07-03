# FinOS — Platform Foundation Security & Risk Review

Review of the transaction/sync foundation across four axes — security, scalability, data
consistency, and offline sync — with fixes **already applied** in this layer and residual
risks tracked for later phases. Complements [SECURITY.md](../SECURITY.md).

Legend: ✅ fixed/enforced now · 🟡 partially addressed · ⏳ deferred (tracked).

---

## 1. Security risks

| # | Risk | Status | Control in this foundation |
|---|---|---|---|
| S1 | **Broken object-level authorization** (one user reads/writes another's data) | ✅ | Every repository query is scoped by `user_id`; services take the authenticated id from the JWT, never from the client. Regression test `test_tenant_isolation`. |
| S2 | Client forging aggregates/balances | ✅ | Balances and all report totals are **recomputed server-side** from ledger entries; the client cannot submit a balance. |
| S3 | Mass-assignment / field injection on writes | ✅ | Pydantic schemas whitelist fields; ORM objects are never populated from raw request bodies; responses go through output schemas. |
| S4 | Internal error leakage | ✅ | Uniform error envelope with a correlation id; stack traces logged, never returned ([`errors.py`](../backend/app/core/errors.py)). |
| S5 | Enumerable ids | ✅ | UUIDv7 primary keys (non-sequential) **and** ownership checks — never rely on unguessable ids alone. |
| S6 | AI dependency creeping into the core | ✅ | `domain/` purity + "only `modules/ai` imports `llm/`" enforced by `tests/test_architecture.py`. |
| S7 | Auth still stubbed (dev bypass) | 🟡 | Interface final; real Supabase JWKS verification is the next task. Dev bypass is disabled in prod by config. |
| S8 | Audit tamper / PII in logs | 🟡 | `audit_log` is insert-only by design; the app DB role must be granted no UPDATE/DELETE on it (deploy-time). Amounts kept, secrets excluded from diffs. ⏳ app-level encryption of sensitive free-text fields. |
| S9 | Rate limiting / abuse | ⏳ | Deferred to the API-hardening phase (Redis token buckets; tightest on auth + future AI). |

## 2. Scalability risks

| # | Risk | Status | Control |
|---|---|---|---|
| C1 | Full-table scans on the ledger | ✅ | Composite indexes matching real queries: `(user_id, occurred_at)`, `(user_id, category_id, occurred_at)`, `(user_id, merchant_id, occurred_at)`, `(user_id, account_id, occurred_at)`, `(user_id, server_seq)`. |
| C2 | Offset pagination degrading on large ledgers | ✅ | The transaction list uses **keyset (cursor) pagination** on stable sort keys, not OFFSET. |
| C3 | Balance recomputation cost (`SUM` of entries) grows with history | 🟡 | Correct and indexed today; a cached per-account balance (updated transactionally, reconciled against entries) is the planned optimization. ⏳ |
| C4 | Report recomputation per request | 🟡 | Range-scanned + cheap now; headline cards move to a precomputed `insights` store via events as volume grows ([REPORTING_ENGINE.md](REPORTING_ENGINE.md#6-performance--scale)). ⏳ |
| C5 | Sync pull cost for large datasets | ✅ | Delta by `server_seq > since` with a bounded `limit` and `has_more`; clients page. |
| C6 | Monolith scaling ceiling | 🟡 | Modular monolith with clean seams; the AI/insights modules are the first split candidates (ADR-001). ⏳ |

## 3. Data-consistency risks

| # | Risk | Status | Control |
|---|---|---|---|
| D1 | Floating-point money drift | ✅ | Integer minor units everywhere via the `Money` type; floats are rejected at construction. |
| D2 | Balance/entry divergence | ✅ | Balance is **defined** as the sum of entries; edits/deletes post reversing entries so the sum is always exact (`test_update_reposts_and_keeps_balance_exact`). |
| D3 | Lost or duplicated triggers between modules | ✅ | Transactional **outbox**: events are written in the same DB transaction as the state change; delivery is at-least-once with idempotent handlers. |
| D4 | Audit divergence from state | ✅ | Audit rows are written in the same transaction as the change. |
| D5 | `server_seq` collisions under concurrency | ✅ | Allocated under a row lock (`FOR UPDATE` on Postgres; SQLite serializes writers). |
| D6 | Partial writes on multi-step operations | ✅ | Services run inside one request transaction (`get_session` commits on success, rolls back on error); flushes populate defaults but never commit early. |
| D7 | Cross-currency aggregation errors | ✅ | Reports reject mixed currencies; money arithmetic raises on currency mismatch. |

## 4. Offline-sync risks

| # | Risk | Status | Control |
|---|---|---|---|
| O1 | Primary-key collisions from offline creates | ✅ | Client-generated UUIDv7 ids. |
| O2 | Duplicate writes on retry/replay | ✅ | Idempotent creates (existing id returns the row); `external_ref` for idempotent ingestion. |
| O3 | Lost updates (blind overwrite) | ✅ | `version` + `base_version` conflict detection; stale writes return `conflict` with the server row instead of overwriting. |
| O4 | Lost deletes | ✅ | Soft-delete tombstones sync like any change. |
| O5 | Clock skew across devices | ✅ | Ordering uses server `server_seq`/`updated_at`, never client clocks. |
| O6 | Client stuck / corrupted local DB | ✅ | Full-sync recovery via `since=0` rebuilds from the server. |
| O7 | Naive datetime tz bugs (SQLite round-trip) | ✅ | Timestamps coerced to UTC before tz conversion in fact-building. |
| O8 | Conflict policy too simplistic long-term | 🟡 | LWW + append-only bias is safe for the single-user/few-device reality; centralized so it can become field-level merge without touching modules. ⏳ |

## 5. Fixes applied in this pass (summary)

- Object-level authorization enforced in every repository and covered by a regression test.
- Server-authoritative balances and report totals (no client-trusted numbers).
- Immutable, append-only ledger with reversing entries → exact balances + full history.
- Transactional outbox + in-same-transaction audit → no lost triggers or audit drift.
- Locked, monotonic `server_seq` → safe concurrent sync cursor allocation.
- Keyset pagination + composite indexes → scalable ledger reads.
- Version-based conflict detection → no silent lost updates offline.
- Architecture tests → domain purity and the AI wall are enforced, not just documented.

## 6. Tracked residual work (by phase)

1. **Auth**: replace the dev bypass with Supabase JWKS verification + JIT user provisioning.
2. **DB hardening**: least-privilege role; `audit_log` and `ledger_entries` granted
   INSERT/SELECT only; optional Postgres RLS as a defense-in-depth backstop.
3. **Rate limiting & abuse controls** (Redis) on auth and (later) AI endpoints.
4. **App-level encryption** of the most sensitive free-text fields (notes, external refs).
5. **Performance**: cached balances and precomputed insight cards as volume grows.
6. **Sync**: field-level merge option if multi-device editing conflicts become common.
