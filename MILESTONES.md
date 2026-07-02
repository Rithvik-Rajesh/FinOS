# FinOS — Milestone Plan

Phased delivery from research to integrations. Each phase lists **Goals, Deliverables,
Acceptance criteria, Risks, and Estimated effort**.

**How to read effort:** ranges are person-weeks assuming a **small team (1–2 engineers)**.
They are planning estimates, not commitments. **Ship Phases 1–2 as the first real release**;
everything after is iterative.

**Global definition of done (every phase):** tests green (unit for `domain/`, integration for
API+DB, widget/golden for mobile), authЗ test proving cross-user isolation, docs updated, a
threat-model glance at new surface, and the feature works **offline** where applicable.

**Sequencing principle:** the calendar/recurring engine (Phase 3) underpins subscriptions
(Phase 4) and cashflow used by the simulator (Phase 6), so its ordering is deliberate.

---

## Phase 0 — Research & setup

**Goals:** de-risk the hard decisions and stand up the skeleton before feature work.

**Deliverables**
- Repo scaffold (`backend/`, `frontend/`, `infra/`, `docs/`) with CI (lint, test,
  secrets/vuln scan) and the **import-lint rule** guarding `llm/` and module boundaries.
- Docker Compose dev env: Postgres, Redis, MinIO; `make up` one-command bring-up.
- Supabase Auth wired: mobile sign-in (email/phone OTP + Google), API JWT verification via
  JWKS, JIT user provisioning.
- **Spikes:** Drift-vs-Isar decision validated ([ADR-002](ARCHITECTURE.md#adr-002--local-database-drift-over-isar)); sync protocol prototype
  (one entity end-to-end offline→online); `Money` value type on both sides.
- Baseline observability (structured logs, health checks) and encrypted-backup runbook.

**Acceptance criteria**
- A signed-in user hits `GET /v1/me`, a local `users` row is JIT-created, JWT rejected when
  invalid/expired.
- One entity round-trips through the sync prototype offline→online with idempotent replay.
- CI blocks a PR that imports `llm/` outside `modules/ai`.

**Risks:** analysis paralysis; over-building infra. **Mitigation:** timebox spikes; Compose
now, orchestration never (until needed).

**Effort:** 2–4 weeks.

---

## Phase 1 — Core expense tracking (first release candidate)

**Goals:** the everyday loop — capture, categorize, understand spending — fully offline.

**Deliverables**
- Entities: `accounts`, `categories`, `merchants`, `transactions` (+ sync/audit mixins).
- Mobile: fast add-expense flow, ledger list, edit/delete (soft), account & category
  management, INR formatting — all offline-first via the local DB + outbox sync.
- **Smart categorization rules** (condition/action DSL) evaluated on device and server;
  rule preview/dry-run.
- **Expense intelligence:** category & merchant **growth** (WoW/MoM/YoY) computed by the
  deterministic engine; dashboard cards ("Food ₹5,000 +18%", "Swiggy ₹2,800 +34%").
- Receipt attachments via presigned MinIO upload (optional per txn).

**Acceptance criteria**
- Add/edit/delete works airplane-mode and reconciles on reconnect with no dupes.
- Growth numbers match hand-computed fixtures (golden tests) across partial periods.
- A rule "merchant=Swiggy → Food" auto-categorizes new and previewed transactions.
- AuthЗ test: user A cannot read/modify user B's transactions.

**Risks:** sync edge cases (clock skew, dupes, conflicts); rule DSL scope creep.
**Mitigation:** centralize sync/conflict logic; keep DSL to a small documented grammar.

**Effort:** 5–8 weeks.

---

## Phase 2 — Goals & budgeting

**Goals:** shift from tracking to progress — budgets and savings goals.

**Deliverables**
- `budgets` + `budget_periods` with cached burn-down; budget-vs-actual + projected
  end-of-period (deterministic).
- `goals` + `goal_contributions`; progress, required-monthly, ETA (computed, cached to
  insights).
- Mobile: budget setup + status, goal creation with target/deadline/priority, progress UI.
- Event wiring: `transaction.created` updates budget burn-down and marks growth stale.

**Acceptance criteria**
- Budget status reflects new expenses within a sync cycle and matches recomputation from the
  ledger.
- Goal projection matches fixtures; changing target/deadline updates required-monthly
  deterministically.
- Works offline with correct reconciliation.

**Risks:** double-counting transfers in budgets/goals. **Mitigation:** transfers excluded
from spend aggregates by rule and tested.

**Effort:** 4–6 weeks.

---

## Phase 3 — Financial calendar (recurrence engine)

**Goals:** future-aware money — recurring items, scheduled instances, cashflow forecast.
This is the backbone for Phases 4 and 6.

**Deliverables**
- `recurring_items` (RRULE) + `scheduled_instances`; Celery Beat materializes a rolling
  horizon.
- Calendar view (rent, EMI, SIP, utilities, bills); mark paid/skip; link a scheduled
  instance to a real transaction.
- **Cashflow forecast** (deterministic) over a horizon; upcoming-bill notifications.

**Acceptance criteria**
- A monthly RRULE materializes correct future instances; editing the rule reflows the
  horizon.
- Forecast equals engine fixtures; a "paid" instance links to its transaction and updates the
  forecast.
- Notifications fire for items due within the reminder window.

**Risks:** RRULE/timezone/DST correctness; notification reliability. **Mitigation:** use a
proven RRULE lib; store TZ explicitly; idempotent notification jobs.

**Effort:** 4–6 weeks.

---

## Phase 4 — Subscription management

**Goals:** control recurring spend — as a **specialization of recurring items**, not a new
subsystem ([ADR-007](ARCHITECTURE.md#adr-007--subscriptions-are-a-specialization-of-recurring-calendar-items)).

**Deliverables**
- Subscription metadata on `recurring_items` (vendor, plan, billing cycle, auto-renew).
- Subscription list + **monthly/annual cost analysis**; renewal reminders; "flag rarely
  used" heuristic (deterministic).
- Optional detection: suggest a subscription when repeated same-merchant/amount charges
  recur.

**Acceptance criteria**
- Monthly & annualized totals are correct across mixed billing cycles.
- Marking a subscription cancelled removes it from future forecast/cost.
- Detection suggestion is confirmable, never auto-applied.

**Risks:** overlap/duplication with Phase 3 if modeled separately. **Mitigation:** it is a
filtered view + analytics over one recurrence engine — enforced.

**Effort:** 2–3 weeks.

---

## Phase 5 — Wealth dashboard (manual)

**Goals:** net worth and allocation — manual entry first.

**Deliverables**
- `assets` + `asset_snapshots` across classes (bank, cash, stock, MF, gold, crypto, FD).
- Net worth (by currency), allocation breakdown, wealth trend over time (deterministic).
- Mobile: add/update holdings and valuations; net-worth card + history.

**Acceptance criteria**
- Net worth = latest snapshot per asset summed by currency; matches fixtures.
- Trend renders from snapshot history; allocation percentages sum to 100%.

**Risks:** manual-entry friction → stale data; scope pull toward live price feeds.
**Mitigation:** keep manual for v1; make snapshot entry fast; live feeds are a later,
separate workstream.

**Effort:** 3–4 weeks.

---

## Phase 6 — Life goal simulator

**Goals:** answer "Can I afford this?" with real consequences.

**Deliverables**
- Deterministic affordability engine combining cashflow (Phase 3), savings rate (Phase 2),
  goals (Phase 2), and emergency-fund runway (Phase 5): outputs cashflow impact, savings-rate
  impact, per-goal delay, emergency-fund impact.
- Funding scenarios (from savings / EMI / pause-a-goal).
- Mobile: purchase input → clear verdict + impact breakdown.

**Acceptance criteria**
- "₹95,000 laptop" returns correct deltas vs a hand-computed scenario across funding modes.
- Every figure is `computed_by: deterministic-engine`; no LLM in the path.

**Risks:** projection assumptions feel arbitrary. **Mitigation:** show assumptions
explicitly; make them adjustable; document the model.

**Effort:** 3–5 weeks.

---

## Phase 7 — AI assistant

**Goals:** a copilot that explains and advises over **already-computed** facts. See
[docs/AI.md](docs/AI.md).

**Deliverables**
- `llm/` provider abstraction (routing, budget, cache, fallback) + `modules/ai`.
- AI **narration** of weekly review & insights (deterministic facts → prose), feature-flagged.
- **Assistant** Q&A with deterministic tool-calling ("where am I overspending?", "can I
  afford this?", "which subs to cancel?", "reach goals faster?").
- Per-user AI budget, safety/disclaimer/number-check post-processing, confirmable
  suggestions.

**Acceptance criteria**
- Disabling AI leaves every core feature fully working (facts still render).
- Post-processor rejects any answer whose figures don't match provided facts/tool outputs.
- Cross-tenant isolation holds under a prompt-injection test; budget exhaustion degrades
  gracefully.

**Risks:** hallucinated numbers, cost runaway, prompt injection, regulatory (advice).
**Mitigation:** hard deterministic wall, number-check, budgets, isolation, non-advice
guardrail + legal review.

**Effort:** 5–8 weeks.

---

## Phase 8 — Integrations (ingestion)

**Goals:** reduce manual entry via automated ingestion — **policy-gated and opt-in**.

**Deliverables (staged, each independently shippable)**
- **Import** (CSV/statement) with idempotent `external_ref` dedupe — lowest risk, do first.
- **SMS ingestion (Android-only, opt-in):** on-device parsing of bank/UPI SMS into draft
  transactions the user confirms. Respect Play Store `READ_SMS` policy; no silent reading.
- **Gmail ingestion (opt-in):** parse receipts/statements; requires Google restricted-scope
  security assessment (CASA).
- **Account Aggregator (RBI):** consented bank data via a licensed TSP/AA — a full compliance
  workstream, gated behind legal/regulatory readiness.

**Acceptance criteria**
- Imports dedupe correctly; re-import is idempotent.
- SMS/Gmail produce **draft** transactions requiring explicit confirmation; consent is
  explicit and revocable; parsing is resilient to unknown formats.
- No ingestion path bypasses categorization rules or authЗ.

**Risks (highest of any phase):** Play Store/Apple policy rejection (SMS), Google CASA cost
& timeline (Gmail), RBI/AA licensing and cost (AA), parser brittleness across banks.
**Mitigation:** start with import; treat SMS/Gmail as opt-in drafts; scope AA only with a
dedicated compliance budget; see [SECURITY.md](SECURITY.md#privacy--regulatory).

**Effort:** import 2–3 weeks; SMS 3–5 weeks; Gmail 4–6 weeks + assessment; AA is a
quarter-scale program, estimate separately.

---

## Suggested release cadence

| Release | Contains | Rationale |
|---|---|---|
| **v0.1 (private beta)** | Phases 0–1 | The core loop must be excellent before anything else. |
| **v0.2** | Phase 2 | Budgets + goals turn tracking into progress — the first "why I stay" hook. |
| **v0.3** | Phases 3–4 | Calendar + subscriptions: forward-looking money. |
| **v0.4** | Phases 5–6 | Wealth + simulator: the "command center" identity. |
| **v1.0** | Phase 7 | AI copilot as the differentiator, on a proven deterministic base. |
| **v1.x** | Phase 8 | Ingestion, gated by policy/regulatory readiness. |
