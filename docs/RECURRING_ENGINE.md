# FinOS — Recurring Engine & Subscription Management

One recurrence abstraction powers recurring expenses, salary, **and** subscriptions
(ADR-007, ADR-010). Pattern detection is deterministic with a confidence score and a
user-approval workflow; occurrences are expanded on read.

Code: pure [`app/domain/recurrence.py`](../backend/app/domain/recurrence.py) +
[`detection.py`](../backend/app/domain/detection.py) +
[`subscriptions.py`](../backend/app/domain/subscriptions.py); persistence
[`app/modules/recurring/`](../backend/app/modules/recurring) &
[`app/modules/subscriptions/`](../backend/app/modules/subscriptions).

---

## The shared model

`RecurringSeries` (`recurring_series`) is the single entity: `kind` (rent/emi/sip/utility/
subscription/salary/other), `direction` (inflow/outflow), amount, `interval`, `anchor_at`,
`next_due_at`, optional account/category/merchant, `status`, and — for subscriptions —
`is_subscription`, `vendor`, `billing_cycle`, `auto_renew`, `cancelled_at`. A subscription
is *not a separate table*; it is a series with `is_subscription = true`.

## Recurrence (deterministic)

Interval-based (daily/weekly/monthly/quarterly/yearly) with **month-end clamping** (Jan 31 →
Feb 28/29 → Mar 31). `occurrence(spec, k)`, `occurrences_between(spec, start, end)`, and
`next_occurrence(spec, after)` are pure and bounded. Full iCal RRULE (BYDAY, …) is a
documented extension — the interface would not change.

## Detection (pattern recognition + confidence)

`detect_patterns(observations)` groups transactions by `(merchant, exact amount)`, computes
the median gap, classifies it into a cadence band, and scores:

```
confidence = round(100 × (0.6 × regularity + 0.4 × min(1, count/6)))
```

where `regularity` is the fraction of gaps within the band. Requires ≥3 occurrences and
confidence ≥50. Grouping on exact amount stops variable-amount merchants (groceries) from
being flagged. Output includes `expected_next` (the following occurrence).

## User-approval workflow

`POST /v1/recurring/detect` creates detected series as **`pending_approval`** (never active).
The user approves (`/approve` → `active`) or cancels (`/cancel`). Re-running detection is
idempotent — an existing series for the same merchant + amount is skipped.

## Missed / upcoming occurrences

`GET /v1/recurring/upcoming?days=` expands active series via the recurrence engine into a
sorted stream of upcoming occurrences. Missed detection compares expected past occurrences
against the ledger (matching merchant transactions) — occurrences are derived, not stored.

## Subscriptions & analytics

Cost normalization is pure (`normalize_cost`, `aggregate_cost`): annual is exact
(`amount × cycles/year`), monthly is `annual ÷ 12`. Endpoints:

- `GET /v1/subscriptions` (series where `is_subscription`),
- `GET /v1/subscriptions/summary` → monthly + annual totals (the ₹3,200 / ₹38,400 example),
- `GET /v1/subscriptions/inactive?days=` → active subs with no merchant transaction in the
  window (from `merchant_last_seen`),
- `GET /v1/subscriptions/renewals?within_days=`,
- `POST /v1/subscriptions/{id}/cancel`.

## Design rationale, tradeoffs, ADRs

- **ADR-007 (one model):** avoids duplicating recurrence/forecast/reminder logic across
  "recurring" and "subscriptions". Subscriptions are a view + analytics.
- **ADR-010 (shared recurrence engine):** interval-based, not RRULE — covers rent/EMI/SIP/
  salary/subscriptions deterministically today; RRULE later without interface change.
- **Approval-gated detection:** matches the product's "no silent obligations" stance and is
  the same pipeline future SMS/bank-ingested observations will feed.
- **Tradeoff:** exact-amount grouping misses variable-but-recurring bills (electricity);
  a future amount-tolerance band is the extension point.

## Future extension points

- SMS / bank-statement observations → the same `detect_patterns` input.
- Amount-tolerance detection for variable bills.
- Materializing occurrences into a table if per-occurrence state (paid/skipped) is needed.
