"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """Basic health check — verifies the service is running."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
    }
