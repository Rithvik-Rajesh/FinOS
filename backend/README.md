# FinOS Backend

FastAPI modular monolith. See [../ARCHITECTURE.md](../ARCHITECTURE.md) for the design and
[../docs/API.md](../docs/API.md) for the API contract.

## Layout

```
app/
├── main.py          # application factory
├── core/            # config, logging, errors, middleware, security, (Money lives in domain/)
├── domain/          # PURE deterministic money engine — no I/O, no LLM
├── llm/             # provider-abstracted AI client (ONLY modules/ai may import)
├── modules/         # feature modules: api/ service/ repository/ models/ events/
├── api/             # HTTP layer: deps + versioned routers (/v1)
├── db/              # SQLAlchemy base + sync/audit mixins
└── workers/         # Celery app + tasks
migrations/          # Alembic
tests/               # unit (domain), smoke (api), architecture-boundary tests
```

## Develop

```bash
uv sync --extra dev            # create .venv and install
uv run uvicorn app.main:app --reload
# -> http://localhost:8000/docs  (dev auth bypass returns a fixed dev user)
```

## Quality gates

```bash
uv run ruff check .            # lint
uv run ruff format .           # format
uv run mypy app                # type-check (strict)
uv run pytest                  # tests
```

`tests/test_architecture.py` enforces the two structural invariants: only `modules/ai`
imports `llm/`, and `domain/` stays pure. Do not weaken them.

## Migrations

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```
