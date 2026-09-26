from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.stats import CalendarSummaryResponse
from app.services.stats_service import get_calendar_summary

router = APIRouter(tags=["calendar"])

@router.get("/summary", response_model=CalendarSummaryResponse)
async def get_summary(
    year: int = Query(..., description="4-digit year"),
    month: int = Query(..., description="Month 1-12"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CalendarSummaryResponse:
    return await get_calendar_summary(db, user, year, month)
