# FinOS — Transaction Engine

The transaction engine is the single source of financial truth. Every balance, report,
and future feature derives from it. This document describes its entities, the posting
model, immutability, categorization, and lifecycle.

Code map:
- Pure engine: [`app/domain/ledger.py`](../backend/app/domain/ledger.py),
  [`money.py`](../backend/app/domain/money.py), [`enums.py`](../backend/app/domain/enums.py)
- Persistence + orchestration: [`app/modules/ledger/`](../backend/app/modules/ledger)
- Accounts: [`app/modules/accounts/`](../backend/app/modules/accounts)

---

## 1. Entities

| Entity | Table | Purpose |
|---|---|---|
| Account | `accounts` | A money container (cash, savings, current, credit card, wallet, investment). |
| Transaction | `transactions` | A user-facing financial record. |
| LedgerEntry | `ledger_entries` | **Immutable** postings; balances are their sum. |
| Category | `categories` | Hierarchical classification (self-referential `parent_id`). |
| Merchant | `merchants` | Normalized payee (with `normalized_name` for matching/dedup). |
| CategorizationRule | `categorization_rules` | User rules that auto-assign category/merchant. |
| AuditLog | `audit_log` | Append-only trail of every money-bearing change. |

Every user-owned row carries `user_id`, `version`, `server_seq`, `deleted_at`,
`created_at`, `updated_at` (the `SyncMixin`). See [DATABASE.md](DATABASE.md).

## 2. Transaction types

`EXPENSE · INCOME · TRANSFER · REFUND · ADJUSTMENT` (see `TransactionType`). Money is
stored as integer **minor units** plus a currency; amounts are positive magnitudes for
every type except `ADJUSTMENT`, which may be signed.

## 3. The posting model (double-entry friendly)

Each transaction is projected by the pure function `build_postings` into one or more
**postings** against accounts. Sign convention is uniform: **positive increases an
account's balance, negative decreases it** — no per-account-type special-casing (a credit
card is simply an account whose balance is normally negative).

| Type | Postings |
|---|---|
| EXPENSE | `[(account, −amount)]` |
| INCOME | `[(account, +amount)]` |
| REFUND | `[(account, +amount)]` |
| ADJUSTMENT | `[(account, ±amount)]` |
| TRANSFER | `[(source, −amount), (dest, +amount)]` — balanced, nets to zero |

Transfers satisfy the strict double-entry invariant (`nets_to_zero`); income/expense are
single-sided because their counterparty is outside the tracked set of accounts. The model
can be extended to full double-entry (income/expense against virtual accounts) without
changing the posting interface.

**Account balance** ≡ `opening_balance + Σ(ledger entries)`. It is always derived, never
stored as truth ([`balances.py`](../backend/app/modules/ledger/balances.py)).

## 4. Immutable history & auditability

Ledger entries are **append-only** — never updated or deleted:

- **Create** posts the transaction's entries (`txn_version = 1`).
- **Edit** of a money-affecting field posts *reversing* entries for the current state,
  then posts the new state's entries (`txn_version = new version`). Balances stay exact
  because reversals net out; the full history of every change is preserved.
- **Delete** is soft (`deleted_at`) and posts reversing entries so balances return to
  their prior value while the record and its history remain.

Every create/update/delete also writes an append-only `audit_log` row **in the same
transaction**, capturing actor, action, entity, a masked diff, and the correlation id.

A worked example (`test_immutable_history_entries_are_appended`): create ₹280 expense →
1 entry; edit to ₹300 → +2 entries (reversal + new) = 3 immutable rows summing to −30000.

## 5. Categorization

On create, if no category is supplied, the engine builds pure `TransactionFacts`
(including timezone-local hour/day-of-week and the merchant/account names) and runs the
user's active rules ([Categorization](#6-see-also)). A matched rule sets the category
(and optionally merchant), records `categorization_source`, and emits a `RuleApplied`
event. See [EVENT_ARCHITECTURE.md](EVENT_ARCHITECTURE.md).

## 6. Accounts, balances, reconciliation

- **Balance**: derived from entries (above); exposed on account reads.
- **Reconciliation**: `POST /v1/accounts/{id}/reconcile` compares the derived balance to a
  user-supplied statement balance and returns the difference; the user corrects with an
  `ADJUSTMENT` transaction (which posts a signed entry).
- **Future bank integrations**: `institution` and `external_ref` fields exist on accounts
  and `external_ref` on transactions gives idempotent ingestion — unused until the Account
  Aggregator workstream.

## 7. Lifecycle & guarantees

- **Idempotency**: creates use client-supplied UUIDv7 ids; a repeated id returns the
  existing row (safe offline replay).
- **Validation**: invalid postings (non-positive magnitudes, self-transfers, missing
  counter account, currency mismatch) raise `TransactionInvalidError` → HTTP 422.
- **Tenant isolation**: every query is scoped to `user_id` in the repository layer.
- **Determinism**: all arithmetic is integer minor-unit math in the pure domain; no
  floats, no LLM.

## 8. See also

- [SYNC_ARCHITECTURE.md](SYNC_ARCHITECTURE.md) — how transactions replicate offline.
- [EVENT_ARCHITECTURE.md](EVENT_ARCHITECTURE.md) — how other modules react.
- [REPORTING_ENGINE.md](REPORTING_ENGINE.md) — how transactions become insights.
- [API.md](API.md) — the REST surface.
