"""Habit routes — CRUD and schedule versioning."""

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.models.user import User as DBUser
from app.schemas.habits import (
    Habit as HabitSchema,
)
from app.schemas.habits import (
    HabitCreate,
    HabitFromSheet,
    HabitList,
    HabitUpdate,
    ScheduleUpdate,
)
from app.schemas.stats import HabitStatsResponse
from app.services import habit_service, stats_service

router = APIRouter()


@router.get("", response_model=HabitList)
async def get_habits(
    include_archived: bool = False,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HabitList:
    habits = await habit_service.get_habits(db, current_user, include_archived)
    return HabitList(habits=habits)


@router.post("", response_model=HabitSchema, status_code=201)
async def create_habit(
    payload: HabitCreate,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.create_habit(db, current_user, payload)


@router.post("/from-sheet", response_model=HabitSchema, status_code=201)
async def create_habit_from_sheet(
    payload: HabitFromSheet,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.create_habit_from_sheet(db, current_user, payload)


@router.get("/{habit_id}", response_model=HabitSchema)
async def get_habit(
    habit_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.get_habit_or_404(db, habit_id, current_user)


@router.patch("/{habit_id}", response_model=HabitSchema)
async def update_habit(
    habit_id: UUID,
    payload: HabitUpdate,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.update_habit(db, habit_id, current_user, payload)


@router.delete("/{habit_id}", status_code=204)
async def archive_habit(
    habit_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await habit_service.archive_habit(db, habit_id, current_user)


@router.post("/{habit_id}/restore", response_model=HabitSchema)
async def restore_habit(
    habit_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.restore_habit(db, habit_id, current_user)


@router.put("/{habit_id}/schedule", response_model=HabitSchema)
async def update_schedule(
    habit_id: UUID,
    payload: ScheduleUpdate,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await habit_service.update_schedule(db, habit_id, current_user, payload)

@router.get("/{habit_id}/stats", response_model=HabitStatsResponse)
async def get_habit_stats(
    habit_id: UUID,
    current_user: DBUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    return await stats_service.get_habit_stats(db, current_user, habit_id)
