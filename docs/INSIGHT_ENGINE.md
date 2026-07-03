# FinOS — Insight Engine

Deterministic, explainable financial insights. Every insight is reproducible arithmetic
with an explicit driver — **no AI, no LLM**. The copilot narrates these; it never
recomputes them.

Code: pure generators [`app/domain/insights.py`](../backend/app/domain/insights.py);
orchestration [`app/modules/insights/`](../backend/app/modules/insights).

---

## Shape

An `Insight` has `category` (spending/goal/budget/subscription/forecast), `severity`
(positive/info/warning/critical), a `title`, an explainable `detail`, an optional `metric`
(Money) and `change_pct`, and structured `data`.

## Categories & generators (pure)

| Generator | Fires when | Example |
|---|---|---|
| `spending_insight` | net spend rose vs the prior period | *"Spending up 23%. Primary driver: Swiggy (+₹1400). Impact: Masters delayed ~1 month."* |
| `goal_insight` | goal behind/at-risk/achieved | *"Masters is behind schedule. Contribute ₹18,400/mo to catch up."* |
| `budget_insight` | budget over/near limit | *"Food overspent by ₹200."* |
| `subscription_insight` | unused subscriptions exist | *"2 unused subscriptions costing ₹500/mo."* |
| `forecast_insight` | balance projected below zero | *"Balance may dip to −₹1,000 around 2026-07-30."* |

Each generator returns `Insight | None` and takes **pre-computed** inputs, so it is trivially
unit-testable (see `tests/test_insights_domain.py`).

## Orchestration

`insights.service.generate` assembles the facts by calling the existing engines once each —
period-to-date spending growth + top-merchant driver, the goal impact of the extra spend
(via `simulation.analyze_goal_impact`), goal projections, budget status, subscription
inactivity, and the 30-day forecast — then ranks the results (severity, then magnitude).
Computed on read (ADR-011): always current, nothing stored.

The flagship insight cross-links three engines deterministically: **spending growth →
driver merchant → goal delay**, exactly matching the product's headline example.

## Design rationale, tradeoffs, ADRs

- **Pure generators + thin orchestration:** the arithmetic that must be trustworthy lives in
  pure functions; the service only gathers and ranks. This keeps insights testable and keeps
  the AI wall intact.
- **On-read (ADR-011):** no stale insight feed; the cost is a fan-out of engine calls, all
  indexed and bounded.
- **Explainability first:** every insight carries its driver in `data`, so the copilot can
  cite it and the UI can drill in.

## Future extension points

- Precompute the feed on the weekly/period tick into a cache for very large accounts.
- More generators (merchant-growth, category-anomaly) — each is an isolated pure function.
- Confidence/priority weighting from user `financial_priority` preferences.
