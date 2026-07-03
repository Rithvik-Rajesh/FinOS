# FinOS — Review Engine

Weekly / monthly / quarterly reviews generated from the deterministic engines and **stored
as snapshots** for historical viewing.

Code: pure [`app/domain/reviews.py`](../backend/app/domain/reviews.py); orchestration +
snapshot [`app/modules/reviews/`](../backend/app/modules/reviews).

---

## Snapshot model

`Review` (`reviews` table) stores the headline metrics as columns (for listing) and the full
breakdown as JSON `payload`. Unique per `(user, period, period_start)` — re-generating a
period **refreshes** the same row rather than duplicating.

Columns: `period`, `period_start/end`, `currency`, `total_spent/income/net`,
`savings_rate_bps`, `payload`, `generated_at`.

## What a review contains

| Period | Highlights (payload) |
|---|---|
| Weekly | total spent, largest category increase, goal progress, budget performance |
| Monthly | savings rate, goal advancement, subscription changes, net cashflow |
| Quarterly | same shape over a quarter |

Every figure comes from an existing engine (reporting totals, `savings_rate`,
`spending_by_category` deltas, goal projections, budget status, subscription summary). The
only genuinely new arithmetic — the **savings rate** — is a pure, tested function
(`savings_rate(income, spending)`), which returns `None` when there is no income (no
divide-by-zero).

## Periods

`period_bounds(period, as_of, offset)` gives deterministic `[start, end]` for the current
period (`offset=0`) or a past one (`offset=-n`) — weekly (Mon–Sun), monthly, quarterly.

## API

`POST /v1/reviews/generate?period=&offset=` (idempotent snapshot) ·
`GET /v1/reviews?period=` (history) · `GET /v1/reviews/{id}`.

## Design rationale, tradeoffs, ADRs

- **Stored snapshots (deliberate exception to ADR-011):** unlike other read-models, reviews
  are *point-in-time records a user browses later*, so they are persisted. Idempotency per
  period keeps them from duplicating while still allowing a refresh.
- **Columns + JSON:** hot metrics are queryable columns; the rich, evolving breakdown is JSON
  so the shape can grow without migrations.
- **Generated on demand / on a tick:** `POST /generate` runs it now; a Celery-beat job will
  generate the previous period automatically at each boundary.

## Future extension points

- Auto-generate on period rollover via Celery beat.
- Period-over-period comparison ("this month vs last month") inside the payload.
- Narrated reviews: the copilot turns a stored snapshot into prose (consumes, never recomputes).
