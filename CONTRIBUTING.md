# Contributing to FinOS

FinOS handles people's financial data. We optimize for **correctness, security, and
maintainability** over speed. Read [ARCHITECTURE.md](ARCHITECTURE.md) and
[SECURITY.md](SECURITY.md) before your first change.

---

## Golden rules

1. **Money is deterministic.** Every user-facing number comes from `backend/app/domain/`
   (pure functions) or its client equivalent. **Never** compute financial figures with an
   LLM, and never with floats — use integer minor units and the `Money` type.
2. **AI is optional.** Only `modules/ai` may import `llm/`. CI enforces this. No core feature
   may depend on the model.
3. **Everything is tenant-scoped.** Every query filters by the authenticated `user_id`,
   server-side, in the repository layer. Add an authЗ test proving user A cannot touch user
   B's data.
4. **Offline-first.** New user-facing mutations must work against the local DB and go through
   the outbox/sync path — not a direct network call from the UI.
5. **No secrets in the repo.** Ever. Use `.env` / the secrets store.

## Branching & commits

- Branch from `main`: `feat/<area>-<short>`, `fix/<area>-<short>`, `docs/…`, `chore/…`.
- **Conventional Commits** (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Small, focused PRs. One logical change each.
- Never commit directly to `main`; open a PR.

## Definition of Done

A change is done when:

- [ ] Tests pass: unit (`domain/`), integration (API+DB), mobile widget/golden as relevant.
- [ ] A cross-user **authЗ test** exists for any new data endpoint.
- [ ] Deterministic logic has golden-file tests; no money math in the AI path.
- [ ] Offline behavior verified for user-facing mutations.
- [ ] Migrations are reversible and reviewed; indexes considered (see
      [docs/DATABASE.md](docs/DATABASE.md#indexing-strategy)).
- [ ] Input validated (Pydantic), output via response schemas (no raw ORM dumps).
- [ ] Docs/ADR updated if behavior or a decision changed.
- [ ] No secrets, no PII/amounts in logs, no new high/critical dependency vulns.

## Backend conventions

- Python 3.12+, FastAPI, SQLAlchemy 2.x **async**, Pydantic v2, Alembic. Deps via `uv`.
- Respect module layering: `api → service → domain/repository`. `domain/` stays pure (no I/O,
  inject clock/randomness).
- Cross-module access goes through a module's `service`, never another module's tables.
- Format/lint with **ruff**; type-check with **mypy** (strict in `domain/`).
- New async work → a Celery task in `workers/`; handlers must be idempotent.

## Mobile conventions

- Flutter, Riverpod v2 (+codegen), GoRouter, Drift, `freezed` models.
- Feature-first structure (`features/<f>/{data,domain,application,presentation}`).
- UI reads from repositories → local DB (Drift `watch`); never call the network from widgets.
- Money via the shared `Money` type + INR formatters; never format raw doubles.
- Tests: unit for logic, widget for screens, golden for money-formatting and key layouts.

## Decision records

Significant or hard-to-reverse decisions get an ADR in `docs/adr/` (context · decision ·
consequences · alternatives). Link it from [ARCHITECTURE.md](ARCHITECTURE.md#10-architecture-decision-records).

## Security & privacy

- Report vulnerabilities privately to `security@<domain>` — never in a public issue.
- Follow [SECURITY.md](SECURITY.md): tenant scoping, encryption, presigned uploads, audit,
  data minimization, DPDP rights (export/delete).
- Any AI change: preserve the deterministic wall, per-user budget, non-advice disclaimer, and
  cross-tenant isolation.

## Code review checklist (reviewer)

- Correctness of financial math (fixtures?), tenant scoping, offline/sync behavior,
  migration safety, error shape consistency, no secret/PII leakage, tests present, docs
  updated. Approve only when the Definition of Done is met.
