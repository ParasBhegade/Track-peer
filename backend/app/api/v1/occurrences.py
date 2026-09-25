"""Occurrences API — Phase 4 Core Tracking Engine."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.occurrences import (
    Occurrence,
    OccurrenceListResponse,
    OccurrenceUpdate,
    TodayResponse,
)
from app.services import occurrence_service

router = APIRouter()


@router.get("/today", response_model=TodayResponse)
async def get_today(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TodayResponse:
    """Get today's occurrences and progress summary."""
    return await occurrence_service.get_today(db, current_user)


@router.get("/occurrences", response_model=OccurrenceListResponse)
async def get_occurrences(
    from_date: date,
    to_date: date,
    habit_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OccurrenceListResponse:
    """Get occurrences in a date range."""
    return await occurrence_service.get_occurrences(db, current_user, from_date, to_date, habit_id)


@router.put("/occurrences/{occurrence_id}", response_model=Occurrence)
async def update_occurrence(
    occurrence_id: UUID,
    payload: OccurrenceUpdate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Occurrence:
    """Update occurrence status with idempotency."""
    return await occurrence_service.update_occurrence(db, current_user, occurrence_id, payload, idempotency_key)
