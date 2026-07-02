# syntax=docker/dockerfile:1
# Multi-stage build using uv for fast, reproducible installs.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first (cached layer), then the app.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --requirement pyproject.toml

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

# Non-root runtime user.
RUN useradd --create-home --uid 10001 finos
USER finos

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
