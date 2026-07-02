# FinOS — AI Architecture

The AI layer is what makes FinOS a *copilot* rather than a ledger. It is also the part most
capable of eroding trust if done wrong. The entire design follows one law:

> **The LLM never produces a number the user relies on.** Deterministic code computes every
> figure. The model explains, prioritizes, narrates, and converses over facts that already
> exist. Remove the model and the app still works.

---

## 1. Separation of concerns (the hard wall)

```mermaid
flowchart TB
    subgraph Deterministic["Deterministic zone (source of truth)"]
        ENG[Financial Calculation Engine\ndomain/ — pure functions]
        INS[insights module\nprecomputed facts]
        ENG --> INS
    end
    subgraph AIZone["AI zone (narration & reasoning only)"]
        CB[Context builder]
        TOOLS[Tool layer\n(calls deterministic engine)]
        PR[Prompt assembler]
        LLM[LLM provider\nvia llm/ abstraction]
        POST[Post-processor\nnumber-check · disclaimer · redaction]
    end
    INS --> CB
    CB --> PR --> LLM --> POST
    LLM <--> TOOLS
    TOOLS --> ENG
    POST --> OUT[Answer to user]
```

- **Only `modules/ai` imports `llm/`.** Enforced by an import-lint check in CI. No budget,
  goal, or affordability number originates in the AI zone.
- Numbers enter the AI zone **only** as (a) precomputed `insights` facts, or (b) return
  values of deterministic **tools** the model may call. The model may quote them; it may not
  invent or recompute them.

## 2. What the AI is used for

| Use case | Model role | Numbers come from |
|---|---|---|
| Weekly review narration | Turn computed deltas into a readable summary | `insights.weekly_review` |
| Insight explanation ("why did Food go up?") | Explain drivers already identified | `insights.growth` + tool: top merchant deltas |
| Assistant Q&A ("where am I overspending?") | Retrieve + reason over facts, suggest actions | tools over ledger/budgets/goals |
| Affordability narration | Explain a deterministic verdict in plain language | `/simulator/affordability` result |
| "Which subscriptions to cancel?" | Rank/reason with justification | subscriptions summary + usage signals |
| Goal coaching | Suggest contribution strategies | goal projection tool |

The AI **never** silently changes data. Any action it proposes (create a rule, adjust a
budget) is surfaced as a **confirmable suggestion**, executed by deterministic code only
after explicit user approval.

## 3. Context management

A budget-bounded context is assembled per request:

1. **User profile snapshot** — base currency, active goals (targets/progress, computed),
   budget status, net-worth summary. Compact, precomputed.
2. **Question-relevant facts** — retrieved from `insights` and via tools scoped to the
   question (e.g. category/merchant growth for "overspending").
3. **Conversation memory** — a rolling summary of the thread, not the raw transcript, to
   cap tokens.
4. **System prompt** — role, the non-advice policy, the "never fabricate numbers" rule,
   the output contract, and the required disclaimer.

**Strict isolation:** context is built **only** from the authenticated user's data. No
cross-tenant data ever enters a prompt. User free-text (notes, merchant names) is treated
as **untrusted input** and is clearly delimited to resist prompt injection; tool calls are
authorized against the same `user_id` server-side, so even a hijacked prompt cannot reach
another user's data.

## 4. Prompt architecture

- **Layered prompts:** `system` (policy + contract, cacheable/stable) → `context` (facts) →
  `user` (question). Keeping the system layer stable enables **prompt caching** for cost.
- **Structured facts, not prose:** facts are passed as compact JSON so the model quotes exact
  values (`"food_mom_delta_pct": 18.0`) rather than paraphrasing numbers.
- **Output contract:** the model returns structured output — a short narrative plus an
  optional list of `suggested_actions` (typed, each mapping to a deterministic operation the
  user can confirm) and `cited_facts` (the fact ids it used). This makes answers auditable.
- **Tool/function calling:** deterministic tools exposed to the model, e.g.
  `get_category_growth`, `get_affordability`, `get_goal_projection`,
  `get_subscription_summary`. Every tool is a thin wrapper over the domain engine, is
  authorized to the current user, and returns exact numbers.

## 5. Provider abstraction (`llm/`)

A single internal interface decouples the app from any vendor:

```
llm/
  client.py        # LLMClient protocol: complete(), stream(), embed()
  providers/
    openai.py
    anthropic.py
  router.py        # model selection by task (cheap model for narration,
                   # stronger model for the assistant), fallback on outage
  budget.py        # per-user + global token/cost accounting and caps
  cache.py         # prompt/response caching keyed on stable inputs
```

- Task-based routing: cheap/fast model for templated narration; stronger model for
  open-ended assistant reasoning.
- Provider fallback: on a provider outage or rate limit, fail over or **degrade gracefully
  to deterministic-only** output.
- Everything is streamed to the client where it improves perceived latency.

## 6. Financial insight generation (deterministic first)

Insights are produced by workers in two stages so AI is optional:

1. **Compute (deterministic):** the `insights` module + engine compute the facts — growth
   deltas, largest movers, savings-rate change, goal progress, forecast — and store them.
   *This stage alone fully powers the UI's insight cards and the weekly review.*
2. **Narrate (optional AI):** if AI is enabled and within budget, a worker asks the model to
   turn those exact facts into friendly prose. If disabled/over-budget, the UI shows the
   deterministic facts with a templated (non-LLM) sentence.

So the "Weekly Financial Review" and growth cards render with or without AI; AI only changes
the *wording*, never the *numbers*.

## 7. Cost optimization

- **Precompute + cache:** narrate insights in batch on the weekly/period tick, not per view.
- **Prompt caching:** stable system layer + templated structures maximize cache hits.
- **Model routing:** cheapest capable model per task; reserve the strong model for the
  interactive assistant.
- **Context compression:** rolling conversation summaries; compact JSON facts; no raw
  transaction dumps into prompts (tools fetch what's needed).
- **Per-user monthly AI budget** with a hard cap; on exhaustion, degrade to deterministic
  output and inform the user. Protects both spend and against cost-bombing (see
  [SECURITY.md](../SECURITY.md#8-rate-limiting--abuse-control)).
- **Global spend ceiling + alerting** so a bug or abuse cannot run away.

## 8. Safety constraints

- **No fabricated numbers:** post-processor validates that figures in the answer match
  provided facts/tool outputs (numbers are tagged); mismatches are stripped or the answer is
  regenerated.
- **Non-advice guardrail:** system prompt forbids specific buy/sell securities
  recommendations; a standing disclaimer is appended; educational framing enforced
  (regulatory — [SECURITY.md](../SECURITY.md#privacy--regulatory)).
- **No autonomous mutations:** the model can only *propose*; deterministic code executes on
  explicit user confirmation.
- **Prompt-injection resistance:** user data delimited and treated as untrusted; tools
  re-authorize server-side; model output treated as untrusted before rendering.
- **PII minimization to providers:** send only what a task needs; where feasible, reference
  entities by opaque ids rather than raw personal detail; document what leaves the region.
- **Auditability:** each AI interaction logs the facts/tools used and the model/version, so
  any answer can be reconstructed and reviewed.
- **Graceful failure:** any AI error falls back to deterministic output — never a broken
  screen, never a blocked core action.
