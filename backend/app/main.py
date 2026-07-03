"""FinOS application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.core.middleware import CorrelationIdMiddleware

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings = get_settings()
    # Register planning-layer event handlers on the outbox dispatcher.
    from app.events.handlers import register_all

    register_all()
    log.info("finos_startup", env=settings.env, version=__version__)
    # Phase 1+: initialize DB engine, Redis pool, MinIO client here.
    yield
    log.info("finos_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="FinOS API",
        version=__version__,
        summary="Personal Finance OS — deterministic money, AI-optional.",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_prod else None,
        redoc_url=None,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/", tags=["system"], summary="Service root")
    async def root() -> dict[str, str]:
        return {"service": "finos", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
