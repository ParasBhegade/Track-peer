"""Standardized error handling.

Implements the error shape from Phase 3 §1:
{
  "error": {
    "code": "...",
    "message": "...",
    "details": [...]
  }
}
"""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Application-level error that maps to a standard JSON error response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(message)


def _error_body(code: str, message: str, details: list[dict[str, Any]] | None = None) -> dict:
    body: dict[str, Any] = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    """Handle AppError → standard JSON shape."""
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.code, exc.message, exc.details),
        headers=exc.headers,
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Remap FastAPI/Pydantic 422 → standard error shape (Phase 3 §1)."""
    details = []
    for err in exc.errors():
        loc = err.get("loc", ())
        # Skip the first element if it's "body"
        field = ".".join(str(part) for part in loc if part != "body")
        details.append({"field": field, "issue": err.get("msg", "")})

    return JSONResponse(
        status_code=422,
        content=_error_body("validation_error", "Validation failed", details),
    )
