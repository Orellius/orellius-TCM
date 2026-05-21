"""Structured error handling for the Orellius backend.

Provides a hierarchy of application exceptions that map to HTTP status codes
and a consistent JSON error response format.
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base application error with HTTP status code and machine-readable code."""

    def __init__(
        self,
        message: str,
        code: str = "app_error",
        status_code: int = 500,
        detail: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.detail = detail


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "not_found"):
        super().__init__(message=message, code=code, status_code=404)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", code: str = "validation_error", detail: str | None = None):
        super().__init__(message=message, code=code, status_code=422, detail=detail)


class AuthError(AppError):
    def __init__(self, message: str = "Authentication required", code: str = "auth_error"):
        super().__init__(message=message, code=code, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", code: str = "forbidden"):
        super().__init__(message=message, code=code, status_code=403)


class TelegramNotConnectedError(AppError):
    def __init__(self):
        super().__init__(
            message="Telegram not connected. Connect first via the Connection tab.",
            code="telegram_not_connected",
            status_code=503,
        )


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        body: dict = {"ok": False, "error": exc.message, "code": exc.code}
        if exc.detail:
            body["detail"] = exc.detail
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(Exception)
    async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled exception:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "Internal server error", "code": "internal_error"},
        )
