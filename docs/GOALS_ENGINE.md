# FinOS — Goals Engine

Savings/purchase/emergency/education/travel/custom goals with deterministic progress,
required-contribution, and completion prediction. Consumes the transaction foundation;
projections are computed on read and never stored.

Code: pure [`app/domain/goals.py`](../backend/app/domain/goals.py); persistence
[`app/modules/goals/`](../backend/app/modules/goals).

---

## Entities

| Entity | Table | Notes |
|---|---|---|
| Goal | `goals` | name, description, goal_type, target, currency, deadline, priority (1–5), status, archived_at |
| GoalContribution | `goal_contributions` | amount, occurred_at, optional `transaction_id` link, note |
| GoalMilestone | `goal_milestones` | intermediate target; `reached_at` set when crossed |
| GoalProjection | *(computed)* | never stored — derived from contributions |

`status ∈ {active, paused, achieved, archived}`. All carry `SyncMixin` (sync-ready).

## Projection model (deterministic)

`project_goal(target, current, deadline, observed_monthly, as_of)`:

- **current** = Σ contributions (from the ledger of contributions).
- **remaining** = max(0, target − current).
- **required_monthly** = ⌈remaining / months_to_deadline⌉ (or the whole remainder when the
  deadline is this month/past).
- **observed_monthly** = Σ(contributions in the trailing 90 days) ÷ 3 — a transparent,
  deterministic rate (no smoothing/regression).
- **projected_completion** = `as_of + ⌈remaining / observed_monthly⌉` months (None when the
  rate is zero → unreachable).
- **health** ∈ `{achieved, ahead, on_track, behind_schedule, at_risk, no_deadline}`:
  `ahead` requires ≥1 month buffer before the deadline; `at_risk` = deadline passed, not met.

Worked (the brief's example): *Masters Abroad* — target ₹15,00,000, current ₹2,75,000,
deadline Aug 2028. `required_monthly` and `projected_completion` follow directly from the
formulas above; if the observed rate lags the required rate, `health = behind_schedule`.

## On-track / behind detection

Purely a comparison of `projected_completion` vs `deadline` (see `_health`). Because the
observed rate is recomputed on every read from real contributions, the status is always
current — there is nothing to recompute on transaction events.

## Milestones & achievement

On each contribution the service marks any milestone whose target is now crossed
(`reached_at`) and flips the goal to `achieved` when `current ≥ target` — both are audited
and version-bumped.

## API

`POST/GET/PATCH/DELETE /v1/goals` · `POST/GET /v1/goals/{id}/contributions` ·
`POST/GET /v1/goals/{id}/milestones` · `GET /v1/goals/{id}/projection`. Filtering by
`status`, pagination, validation, OpenAPI — all standard.

## Design rationale, tradeoffs, ADRs

- **Computed projections (ADR-011):** never store `current`/health; derive from the
  contribution ledger so they cannot drift. Tradeoff: a `SUM` per read — cheap and indexed
  (`(user_id, goal_id)`); precompute later only if profiling demands.
- **Observed rate = trailing 90d ÷ 3:** simple and explainable over statistical smoothing,
  matching the "no statistical magic" rule. Extension point: a pluggable rate estimator.

## Future extension points

- Auto-contributions linked to a recurring SIP series (create a `goal_contribution` on each
  materialized occurrence).
- Link contributions to real transfer transactions (`transaction_id` already present).
- Goal prioritization strategies for surplus allocation (feeds the simulator).
