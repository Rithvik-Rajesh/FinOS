# FinOS — Event Architecture

Modules stay decoupled by communicating through **domain events**: the ledger publishes
facts ("a transaction was created"); other modules subscribe, rather than calling the
ledger directly. This is how goals, budgets, insights, and the calendar will react to
transactions without the ledger ever depending on them.

Code: event *types* (pure) [`app/domain/events.py`](../backend/app/domain/events.py);
mechanism [`app/events/`](../backend/app/events) (bus + outbox).

---

## 1. Events

Frozen, pure dataclasses carrying `user_id`, `occurred_at`, `event_id`, plus payload:

| Event | Emitted when | Key payload |
|---|---|---|
| `AccountCreated` | an account is created | account_id, type, currency |
| `TransactionCreated` | a transaction is created | transaction_id, type, amount, account, category, merchant |
| `TransactionUpdated` | a transaction changes | transaction_id, version, changed_fields |
| `TransactionDeleted` | a transaction is soft-deleted | transaction_id |
| `RuleApplied` | rules categorized a transaction | transaction_id, rule_ids, category_id, source |

Every event serializes to a JSON-safe payload via `to_payload()` (UUIDs → str, datetimes
→ ISO, enums → value).

## 2. Two delivery mechanisms

### In-process bus ([`bus.py`](../backend/app/events/bus.py))
An async publish/subscribe bus for **same-process, same-request** reactions. Handlers
subscribe by event type; a failing handler is isolated and logged so it can't break the
publisher or siblings. Use for lightweight, immediate side effects.

### Transactional outbox ([`outbox.py`](../backend/app/events/outbox.py))
The **durable** path. Events are written to the `outbox` table **in the same database
transaction** as the state change that produced them. This is the key reliability
property: *if the change commits, the event is recorded* — no lost triggers. A worker
later reads unpublished rows and delivers them (Celery), giving **at-least-once**
delivery. Because delivery may repeat, **handlers must be idempotent**.

```
create_transaction():
    ── begin tx ──
    persist transaction + immutable entries
    write audit_log row
    enqueue(TransactionCreated)   # same transaction
    enqueue(RuleApplied)          # if rules fired
    ── commit ──                  # state + events commit atomically
        │
        └─▶ Celery drains outbox ─▶ publishes ─▶ subscribers (budgets, insights, ...)
```

## 3. Publishing

The ledger service publishes by calling `enqueue(session, event)` inside its unit of
work. It does **not** know who consumes the event. Adding a consumer never touches the
ledger.

## 4. Consumption (how future modules subscribe)

A future module (e.g. budgets) will:

1. Define a handler `async def on_transaction_created(event) -> None: ...` that is
   **idempotent** (safe to run more than once).
2. Register it — on the in-process bus for immediate reactions, or as an outbox consumer
   (a Celery task keyed by event name) for durable, cross-process reactions.
3. React using only the event payload (or by calling the owning module's *service*),
   never by reaching into the ledger's tables.

Example reactions this design enables without modifying the ledger:
- `budgets`: on `TransactionCreated` → update burn-down.
- `insights`: on `TransactionCreated`/`period.rolled` → mark growth stale / recompute.
- `calendar`: on `TransactionCreated` → match to a scheduled recurring item.
- `ai` (optional): on `weekly.tick` → narrate the review.

## 5. Design rules

- Event **definitions live in the domain** (pure, no I/O); the **mechanism lives in
  `app/events`** (may touch the DB, never the domain).
- Producers depend on events, not consumers. Consumers depend on events, not producers.
- Handlers are **idempotent** and **isolated** (one failure never blocks others).
- The outbox is the source of truth for "did this event happen"; the in-process bus is a
  convenience for immediate, best-effort reactions.

## 6. Why not a message broker (yet)

At this scale a transactional outbox drained by Celery gives the reliability we need
(atomic with the state change, at-least-once, replayable) without the operational cost of
Kafka/RabbitMQ. The outbox is broker-agnostic: if throughput ever demands it, the drainer
can publish to a real broker with no change to producers or event definitions.
