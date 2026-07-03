# FinOS — Notification Engine

Event-driven, queue-based notifications with **no vendor lock-in**. Deterministic generation
from the planning engines; delivery behind a swappable notifier.

Code: [`app/modules/notifications/`](../backend/app/modules/notifications).

---

## Entities

| Entity | Table | Role |
|---|---|---|
| NotificationRule | `notification_rules` | *What* to notify about + thresholds (per user, per type; `enabled`, `lead_time_days`, `params`) |
| NotificationPreference | `notification_preferences` | *How* to deliver (per user: in-app/push/email toggles, quiet hours) |
| NotificationEvent | `notification_events` | The queue (idempotent per `dedupe_key`) |

Supported types: goal reminder, budget warning, subscription renewal, upcoming bill,
forecast warning, goal completion.

## Generation (the scan)

`scan(user_id, currency)` is the deterministic generator. It walks the engines and enqueues
events, each with a **dedupe key** so re-runs never duplicate:

- **Upcoming bills / subscription renewals** — recurring occurrences within the rule's
  `lead_time_days` → `{type}:{series}:{due_date}`.
- **Budget warnings** — over/warning budget status → `budget_warning:{budget}:{period}:{level}`.
- **Goal reminders / completions** — behind/at-risk or achieved projections →
  `goal_reminder:{goal}:{month}` / `goal_completion:{goal}`.
- **Forecast warnings** — projected negative balance → `forecast_warning:{month}`.

It runs on **Celery beat** and/or on demand (`POST /v1/notifications/scan`). Rules gate what
fires; the preference picks the channel.

## Delivery (vendor-neutral)

A `Notifier` protocol delivers a queued event. `InAppNotifier` is a no-op — the queued row
*is* the in-app notification the client reads. Push (FCM/APNs) and email (SES/…) implement
the same protocol later **without touching the queue or generators** — no vendor is baked
into the schema.

## Event-driven integration

The scan reuses the same deterministic outputs as the rest of the platform and is
idempotent, so it composes with the existing transactional outbox + dispatcher: a
`TransactionCreated` (already consumed for budget alerts) can trigger a scan, and a beat job
runs it periodically. The queue decouples generation from delivery.

## API

`GET /v1/notifications` (feed) · `POST /v1/notifications/scan` ·
`GET/PATCH /v1/notifications/rules[/{type}]` · `GET/PATCH /v1/notifications/preferences` ·
`POST /v1/notifications/{id}/read|dismiss`.

## Design rationale, tradeoffs, ADRs

- **Three entities, clean split:** *rules* (what/threshold) vs *preferences* (how) vs *events*
  (queue) keeps configuration and delivery orthogonal.
- **Idempotent dedupe keys:** at-least-once generation is safe; no duplicate spam.
- **Notifier protocol:** the anti-lock-in seam — channels are pluggable.

## Future extension points

- Push/email notifiers implementing `Notifier`.
- Quiet-hours enforcement + scheduled delivery (`scheduled_for`).
- Per-rule custom thresholds via `params`.
