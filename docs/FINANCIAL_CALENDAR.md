# FinOS — Financial Calendar

A computed, ordered stream of future financial events — bills, subscriptions, EMIs, salary,
recurring expenses, goal milestones, and budget checkpoints — aggregated from the other
planning modules. Nothing is stored; the calendar always reflects current definitions.

Code: [`app/modules/calendar/`](../backend/app/modules/calendar).

---

## FinancialEvent (computed)

`{type, title, occurs_at, amount, direction, source_kind, source_id}` where
`type ∈ {bill, subscription, emi, goal_milestone, budget_checkpoint, salary,
recurring_expense}`.

## Sources & aggregation

`build_events(user_id, start, end)` composes:

1. **Recurring occurrences** — active `RecurringSeries` expanded via the recurrence engine;
   the event type is derived from `kind`/`is_subscription` (rent/utility → bill, emi → emi,
   salary → salary, subscription → subscription, else recurring_expense).
2. **Goal deadlines** — active goals with a deadline in range → `goal_milestone`.
3. **Budget checkpoints** — each active budget's period-end dates in range →
   `budget_checkpoint` (bounded scan of periods).

Events are returned sorted by `occurs_at`, with rolled-up `upcoming_outflow` and
`upcoming_inflow` totals for the window.

## Views

`GET /v1/calendar?days=&currency=` returns the ordered stream for the next N days. **Daily /
weekly / monthly views are derived client-side** by grouping this stream — the server
returns one canonical, ordered dataset rather than three near-duplicate endpoints. Future
obligations (upcoming expenses, income, renewals) are the outflow/inflow/subscription slices
of the same stream.

## Design rationale, tradeoffs, ADRs

- **Computed aggregation (ADR-011):** the calendar is a *projection* of goals + budgets +
  recurring series, so it is derived on read and cannot go stale. No `financial_events` table.
- **One ordered stream, client-side grouping:** avoids three overlapping endpoints and keeps
  the grouping logic (timezone-aware day/week/month) on the client that renders it.
- **Tradeoff:** each call fans out across modules. Windows are bounded (≤366 days) and the
  underlying reads are indexed; a cached materialization is the extension point if needed.

## Future extension points

- Persisted per-occurrence state (paid/skipped/overdue) if the calendar becomes actionable.
- iCal/Google Calendar export of the event stream.
- Notifications for imminent bills/renewals (consume the same stream from a worker).
