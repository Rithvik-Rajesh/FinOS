# FinOS — Personal Finance OS

> A mobile-first **personal financial command center**, not an expense tracker.
> FinOS helps people understand where their money goes, whether they are
> progressing toward their goals, what they can afford, and what to do next.

**Status:** Pre-implementation. This repository currently contains the
**design and planning package** only. See the documents below before writing code.

---

## Philosophy

People do not care about recording expenses. They care about **decisions**:

- Where is my money going, and is that changing?
- Am I on track for my goals?
- Can I afford this?
- What should I do next?

Every feature is judged against one question: *does it help the user make a better
financial decision?* Bookkeeping is a means, never the product.

## Product principles (non-negotiable)

| Principle | What it means in practice |
|---|---|
| **Mobile-first** | The phone is the primary client. The backend serves the phone, not the reverse. |
| **Offline-first** | Core flows (add/edit expense, view dashboard) work with no network. Sync is a background concern. |
| **Deterministic money** | Every number the user sees is computed by tested, deterministic code. **LLMs never do arithmetic.** |
| **AI-optional** | The app is fully useful with AI disabled. AI explains and suggests; it is never load-bearing. |
| **Security & privacy first** | Financial data is among the most sensitive PII. Encrypt, minimize, audit, consent. |
| **India-first** | INR, Indian payment/merchant patterns, DPDP Act compliance. Global is a later data-model detail, not a rewrite. |

## Documentation map

Read in this order:

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** — system, backend, mobile, and AI architecture; major design decisions and tradeoffs.
2. **[SECURITY.md](SECURITY.md)** — threat model, auth, encryption, top risks and mitigations, privacy & compliance.
3. **[docs/DATABASE.md](docs/DATABASE.md)** — entities, ERD, indexing, soft-delete and audit strategy.
4. **[docs/API.md](docs/API.md)** — REST design, versioning, errors, sync protocol.
5. **[docs/AI.md](docs/AI.md)** — deterministic-vs-LLM separation, prompt/context architecture, cost & safety.
6. **[MILESTONES.md](MILESTONES.md)** — phased delivery plan (Phase 0–8) with acceptance criteria and effort.
7. **[CONTRIBUTING.md](CONTRIBUTING.md)** — how we work, conventions, definition of done.

## Tech stack (target)

| Layer | Choice | Notes |
|---|---|---|
| Mobile | Flutter, Riverpod, GoRouter | Local DB: **SQLite via Drift** recommended over Isar — see [ARCHITECTURE.md](ARCHITECTURE.md#adr-002--local-database-drift-over-isar). |
| Backend | FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2 | Async everywhere. |
| Database | PostgreSQL 16 | Money as integer minor units; append-only audit. |
| Auth | Supabase Auth (managed) | JWT validated at the API via JWKS; app data stays in **our** Postgres. |
| Object storage | MinIO (S3-compatible) | Receipts/attachments, presigned uploads. |
| Jobs | Celery + Redis | Recurring-txn materialization, weekly reviews, insight precompute. |
| AI | Provider-abstracted (OpenAI / Anthropic) | Behind an internal `llm` interface; swappable, budgeted, optional. |
| Hosting | Hetzner VPS + Docker Compose | Grows to managed Postgres / k8s only if scale demands it. |

## Repository structure

```
finos/
├── README.md                 # This file
├── ARCHITECTURE.md           # System architecture & ADRs
├── SECURITY.md               # Security & privacy architecture
├── CONTRIBUTING.md           # How we work
├── MILESTONES.md             # Phased delivery plan
├── docs/                     # Deep-dive design docs + ADRs
│   ├── DATABASE.md
│   ├── API.md
│   ├── AI.md
│   └── adr/                  # Architecture Decision Records
├── backend/                  # FastAPI service (see ARCHITECTURE.md)
│   ├── app/
│   │   ├── core/             # config, security, logging, errors
│   │   ├── domain/           # pure business logic (the "money engine")
│   │   ├── modules/          # feature modules (expenses, goals, ...)
│   │   ├── api/              # HTTP layer (routers, schemas, deps)
│   │   ├── workers/          # Celery tasks
│   │   └── db/               # models, migrations, session
│   ├── tests/
│   └── pyproject.toml
├── frontend/                 # Flutter app (feature-first)
│   ├── lib/
│   │   ├── core/             # theme, router, network, db, di
│   │   ├── features/         # one folder per feature (expenses, goals, ...)
│   │   └── shared/           # reusable widgets, formatters
│   └── pubspec.yaml
└── infra/                    # Docker, compose, CI, provisioning
    ├── docker/
    ├── compose/
    └── ci/
```

Every directory is explained in [ARCHITECTURE.md](ARCHITECTURE.md#9-repository-structure).

## Local development (once implemented)

> Not yet runnable. Target developer experience:

```bash
# Backend + infra
cp .env.example .env
docker compose -f infra/compose/dev.yml up -d   # postgres, redis, minio
cd backend && uv sync && alembic upgrade head && uvicorn app.main:app --reload

# Mobile
cd frontend && flutter pub get && flutter run
```

## License

TBD (private during initial development).
