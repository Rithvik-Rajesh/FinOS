"""Liveness and readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    """Process is up. Does not check dependencies."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=HealthResponse, summary="Readiness probe")
async def ready() -> HealthResponse:
    """Ready to serve. Phase 1+ will also check Postgres/Redis/MinIO connectivity."""
    return HealthResponse(status="ready", version=__version__)
