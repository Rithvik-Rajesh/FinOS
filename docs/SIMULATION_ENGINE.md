# FinOS — Simulation (Financial Decision) Engine

Deterministic "what-if" math the future AI assistant will *call* but never replace:
purchase affordability, EMI amortization, and goal-impact analysis. Every output is
reproducible arithmetic — no advice, no heuristics, no model.

Code: pure [`app/domain/simulation.py`](../backend/app/domain/simulation.py); orchestration
[`app/modules/simulation/`](../backend/app/modules/simulation).

---

## EMISimulation

`compute_emi(principal, annual_rate_bps, months)` — standard reducing-balance amortization
via `Decimal` (rounded to minor units): `EMI = P·r·(1+r)ⁿ / ((1+r)ⁿ − 1)`, with the
zero-interest case handled. Returns `monthly_payment`, `total_payment`, `total_interest`.
`POST /v1/simulations/emi`.

## GoalImpactAnalysis

`analyze_goal_impact(goal, reduce_current_by, as_of)` re-projects a goal after diverting
cash from its savings and reports `baseline_completion`, `impacted_completion`, and
`delay_months` — computed by running the pure goals engine twice.

## PurchaseSimulation

`POST /v1/simulations/purchase` assembles inputs from the platform and runs
`simulate_purchase`:

- **cash impact** — `cash_after = cash_before − amount` (cash funding) or unchanged (EMI).
- **emergency-fund impact** — `affordable_from_cash` = cash stays ≥ the emergency-fund goal
  target (the floor).
- **goal impact** — per active goal, the delay from a cash drawdown (empty when EMI-financed).
- **budget / subscription / forecast impact** — available from the same computed engines
  ([FORECASTING_ENGINE.md](FORECASTING_ENGINE.md), [BUDGET_ENGINE.md](BUDGET_ENGINE.md)).
- **financing** — with `funding="emi"`, cash is untouched and `monthly_surplus` drops by the
  EMI.

The brief's example ("₹95,000 laptop") returns cash-after, affordability vs the emergency
floor, and each goal's delay — all deterministic and reproducible.

## Design rationale, tradeoffs, ADRs

- **Composed from the other pure engines:** the simulator adds no new financial math — it
  orchestrates goals/forecasting/budgets so a scenario is exactly "the platform, with one
  input changed". This is why it is safe for the AI to call.
- **Monthly surplus = trailing-90d net ÷ 3; emergency floor = the emergency-fund goal
  target:** explainable inputs over inferred ones.
- **Tradeoff:** a purchase paid from cash is modeled as reducing every goal's headroom
  uniformly; per-goal funding rules (priority-based allocation) are the extension point.

## The AI boundary

The assistant calls this engine for the numbers and only narrates the result. The
architecture test guarantees the deterministic engines never import the LLM layer, so a
simulated figure can never be model-generated.

## Future extension points

- Priority-based surplus/goal allocation strategies.
- Multi-item / recurring-purchase scenarios.
- Refinance / prepayment EMI variants.
