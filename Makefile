# FinOS developer entrypoints. Run `make help` for the list.
.DEFAULT_GOAL := help
COMPOSE := docker compose -f infra/compose/dev.yml --env-file .env

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ---- Environment ----
.PHONY: env
env: ## Create .env from .env.example if missing
	@test -f .env || (cp .env.example .env && echo "created .env — review the values")

.PHONY: up
up: env ## Start dev infra (postgres, redis, minio)
	$(COMPOSE) up -d

.PHONY: down
down: ## Stop dev infra
	$(COMPOSE) down

.PHONY: nuke
nuke: ## Stop dev infra AND delete volumes (destroys local data)
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail dev infra logs
	$(COMPOSE) logs -f

# ---- Backend ----
.PHONY: backend-install
backend-install: ## Install backend deps
	cd backend && uv sync --extra dev

.PHONY: backend-run
backend-run: ## Run the API with reload
	cd backend && uv run uvicorn app.main:app --reload

.PHONY: backend-test
backend-test: ## Run backend tests
	cd backend && uv run pytest

.PHONY: backend-lint
backend-lint: ## Lint + type-check the backend
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app

.PHONY: backend-fmt
backend-fmt: ## Auto-format the backend
	cd backend && uv run ruff check --fix . && uv run ruff format .

.PHONY: migrate
migrate: ## Apply DB migrations
	cd backend && uv run alembic upgrade head

# ---- Frontend ----
.PHONY: frontend-install
frontend-install: ## Fetch Flutter packages
	cd frontend && flutter pub get

.PHONY: frontend-run
frontend-run: ## Run the Flutter app
	cd frontend && flutter run

.PHONY: frontend-test
frontend-test: ## Run Flutter tests
	cd frontend && flutter test

.PHONY: frontend-lint
frontend-lint: ## Analyze the Flutter app
	cd frontend && flutter analyze

# ---- Aggregate ----
.PHONY: check
check: backend-lint backend-test ## Run all backend quality gates
