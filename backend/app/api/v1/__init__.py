"""API v1 router aggregation.

Feature modules register their routers here as they are built (Phase 1+). URI versioning
(`/v1`) per docs/API.md#versioning-strategy.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, me

api_router = APIRouter(prefix="/v1")
api_router.include_router(health.router)
api_router.include_router(me.router)

# As modules land they mount here, e.g.:
# from app.modules.ledger.api import router as ledger_router
# api_router.include_router(ledger_router)
