# FinOS — Forecasting Engine

Deterministic, scenario-safe cash-flow forecasting. No AI, no statistical magic — a
day-by-day simulation over scheduled events and an observed spend rate, with **every
assumption returned alongside the result**.

Code: pure [`app/domain/forecasting.py`](../backend/app/domain/forecasting.py); orchestration
[`app/modules/forecasting/`](../backend/app/modules/forecasting).

---

## Inputs (all deterministic)

| Input | Source |
|---|---|
| Starting balance | Σ account balances (derived from the immutable ledger) |
| Recurring cash events | active `RecurringSeries` expanded over the horizon, signed by direction |
| Daily discretionary spend | Σ(spending in trailing 90 days) ÷ 90 |
| Goal contributions | goal projections (completion dates) |
| Budget allocations | budget status (exhaustion dates) |

## The simulation

`forecast_cash(starting_balance, events, daily_discretionary_minor, as_of, horizon_days)`
walks each day: apply that day's scheduled events, subtract the daily discretionary rate,
and track the running balance. It returns:

- **ending_balance**, **min_balance** + **min_balance_date** (the "will I dip / go negative"
  signal), **projected_negative**,
- **total_inflows / total_outflows**,
- a sampled **timeline** (weekly points incl. start and end),
- **assumptions** — an explicit list (events occur as scheduled, the discretionary rate, no
  unplanned income, no interest/fees/market movement).

## Outputs (the full bundle)

`GET /v1/forecast?horizon=30d|90d|180d|1y&currency=` returns the cash forecast **plus**:

- **goal_completions** — projected completion date per active goal,
- **budget_exhaustions** — earliest projected exhaustion per active budget,
- **subscription_monthly / subscription_annual** — normalized subscription cost.

Horizons: 30 / 90 / 180 / 365 days.

## Design rationale, tradeoffs, ADRs

- **Day-by-day integer simulation** over closed-form formulas: transparent, handles
  arbitrary event schedules, and stays in integer minor units (no float drift). Bounded to
  ≤3 years.
- **Transparent assumptions:** returned with every forecast so the UI (and the future AI
  assistant) can state them plainly — satisfies "keep assumptions transparent".
- **Observed discretionary = 90d ÷ 90:** a single, explainable rate. Tradeoff: it doesn't
  model seasonality; a seasonal/rolling estimator is the documented extension point.
- **Scenario-safe:** the engine is pure, so the simulator ([SIMULATION_ENGINE.md](SIMULATION_ENGINE.md))
  runs "what-if" forecasts by adjusting inputs, never by mutating data.

## Future extension points

- Interest/APR on savings and credit-card balances.
- Seasonal discretionary modeling (still deterministic, still assumption-stated).
- Confidence bands via multiple explicit scenarios (best/expected/worst), not statistics.
