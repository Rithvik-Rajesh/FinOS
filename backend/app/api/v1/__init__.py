"""API v1 router aggregation.

Feature modules register their routers here. URI versioning (`/v1`) per
docs/API.md#versioning-strategy.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health, me
from app.modules.accounts.api import router as accounts_router
from app.modules.categories.api import router as categories_router
from app.modules.ledger.api import router as transactions_router
from app.modules.merchants.api import router as merchants_router
from app.modules.reporting.api import router as reports_router
from app.modules.rules.api import router as rules_router
from app.modules.sync.api import router as sync_router

api_router = APIRouter(prefix="/v1")
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(accounts_router)
api_router.include_router(categories_router)
api_router.include_router(merchants_router)
api_router.include_router(transactions_router)
api_router.include_router(rules_router)
api_router.include_router(reports_router)
api_router.include_router(sync_router)
