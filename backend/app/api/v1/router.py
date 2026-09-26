"""API v1 router — aggregates all sub-routers under /api/v1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.calendar import router as calendar_router
from app.api.v1.habit_sheets import router as habit_sheets_router
from app.api.v1.habits import router as habits_router
from app.api.v1.health import router as health_router
from app.api.v1.occurrences import router as occurrences_router
from app.api.v1.stats import router as stats_router
from app.api.v1.users import router as users_router

api_v1_router = APIRouter()

# Health check — no auth required
api_v1_router.include_router(health_router)

# Auth
api_v1_router.include_router(auth_router, prefix="/auth")

# Profile
api_v1_router.include_router(users_router, prefix="/users")

# Habits
api_v1_router.include_router(habits_router, prefix="/habits")
api_v1_router.include_router(habit_sheets_router, prefix="/habit-sheets")

# Occurrences
api_v1_router.include_router(occurrences_router)

# Stats & Calendar
api_v1_router.include_router(stats_router, prefix="/stats")
api_v1_router.include_router(calendar_router, prefix="/calendar")
