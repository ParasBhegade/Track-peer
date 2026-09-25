"""Habit sheets routes — GET /api/v1/habit-sheets."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.models.sheet import HabitSheet
from app.models.user import User as DBUser
from app.schemas.habits import HabitSheetList

router = APIRouter()


@router.get("", response_model=HabitSheetList)
async def get_habit_sheets(
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HabitSheetList:
    stmt = (
        select(HabitSheet)
        .options(selectinload(HabitSheet.habits))
        .order_by(HabitSheet.sort_order)
    )
    result = await db.execute(stmt)
    sheets = list(result.scalars().all())
    return HabitSheetList(sheets=sheets)
