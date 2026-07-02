"""Consistent error envelope and exception handlers (see docs/API.md#error-handling).

Every error response has the same shape and a correlation id; internals never leak.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    """Base class for expected, mapped application errors."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str, *, details: list[dict[str, Any]] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class UnauthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


def _envelope(
    *, code: str, message: str, correlation_id: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "correlation_id": correlation_id,
        }
    }


def _correlation_id(request: Request) -> str:
    return getattr(request.state, "correlation_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                code=exc.code,
                message=exc.message,
                correlation_id=_correlation_id(request),
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in e["loc"]), "issue": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_envelope(
                code="validation_error",
                message="Request validation failed.",
                correlation_id=_correlation_id(request),
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the real cause under the correlation id; never leak internals to the client.
        log.error(
            "unhandled_exception",
            correlation_id=_correlation_id(request),
            error=str(exc),
            exc_info=exc,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                code="internal_error",
                message="An unexpected error occurred.",
                correlation_id=_correlation_id(request),
            ),
        )
