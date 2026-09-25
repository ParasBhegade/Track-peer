"""Habit Tracker — FastAPI application entry point.

Creates the FastAPI app, mounts routers, and registers error handlers.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import AppError, app_error_handler, validation_error_handler


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="Habit Tracker API",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )

    # ── CORS ─────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Error handlers ───────────────────────────────────
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(
        RequestValidationError, validation_error_handler  # type: ignore[arg-type]
    )

    # ── Routers ──────────────────────────────────────────
    application.include_router(api_v1_router, prefix="/api/v1")

    return application


app = create_app()
