# FinOS — Reporting Engine

Deterministic analytics over transactions. **No AI, no floats for money** — these
functions are the canonical definitions of every headline number, and future AI features
*consume* their outputs rather than recomputing them.

Code: pure calculations [`app/domain/reporting.py`](../backend/app/domain/reporting.py);
orchestration [`app/modules/reporting/`](../backend/app/modules/reporting).

---

## 1. Separation of concerns

```
transactions ──▶ ledger/records.py ──▶ TransactionRecord (pure) ──▶ domain/reporting.py
                                                                          │
                                                        reporting/service.py ──▶ REST
```

- The **pure layer** (`domain/reporting.py`) takes lists of `TransactionRecord` value
  objects and returns totals/groups/growth. It has no database and no AI, and is unit
  tested to the rupee.
- The **service layer** loads records (via the ledger's `reporting_records`, so the
  transaction table stays owned by the ledger) and calls the pure functions.

## 2. Conventions

- **Net spending**: `EXPENSE` increases spending, `REFUND` decreases it. `TRANSFER` and
  `ADJUSTMENT` are excluded from spending and income; `INCOME` feeds income only.
- **Single currency per report**: mixed-currency inputs are rejected (`CurrencyMismatch`).
- **Integer minor units** throughout; percentages use `Decimal`, rounded deterministically.

## 3. Calculations

| Function | Result |
|---|---|
| `total_spending` / `total_income` / `net_cashflow` | Money totals |
| `spending_by_category` / `spending_by_merchant` | `GroupTotal[]`, largest first, stable ordering |
| `totals_by_period(period, tz)` | `PeriodTotal[]` bucketed by local day/week/month/year |
| `growth(current, previous)` | delta + `pct_change` (`Decimal`, 1 dp) or `None` when no prior base, plus `is_new` |

Period bucketing is timezone-aware (default **Asia/Kolkata**, India-first): a transaction
is placed in the local calendar period of its `occurred_at`.

## 4. Growth (period-to-date)

`GET /v1/reports/growth?window=wow|mom|yoy` compares the current period **to date**
against the equivalent to-date window in the prior period, so mid-month comparisons are
fair (the first 10 days of this month vs the first 10 days of last month). This is what
powers cards like *"Food ₹5,000 · +18% vs last month"*. Zero-base periods return
`pct_change: null` with `is_new: true` rather than dividing by zero.

## 5. API

| Endpoint | Returns |
|---|---|
| `GET /v1/reports/summary` | spending, income, net for a range |
| `GET /v1/reports/spending?group_by=category\|merchant` | grouped totals |
| `GET /v1/reports/timeseries?period=week\|month` | period buckets |
| `GET /v1/reports/growth?window=wow\|mom\|yoy` | growth vs the prior period |

All are tenant-scoped and currency-parameterized (default `INR`).

## 6. Performance & scale

- Reports are range-scanned over the composite transaction indexes
  (`(user_id, occurred_at)`, `(user_id, category_id, occurred_at)`, etc.).
- The pure functions are cheap and cacheable. As data grows, headline cards should be
  **precomputed by a worker** into an `insights` store (on `TransactionCreated` /
  period-roll events) and served from cache — the calculations themselves never change,
  only where they run. This is the seam the AI assistant will read from.

## 7. Guarantees for AI

Because every number is produced here deterministically, the future AI assistant can
quote figures without ever performing arithmetic. The AI wall (only `modules/ai` may import
`llm/`, enforced by architecture tests) keeps this boundary intact.
