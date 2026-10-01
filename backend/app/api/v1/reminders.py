from datetime import date, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user, get_db
from app.core.errors import AppError
from app.models.habit import Habit
from app.models.occurrence import Occurrence, OccurrenceStatus
from app.models.user import User
from app.schemas.reminders import ReminderItem, ReminderPlanResponse
from app.services.habit_service import _get_local_today, resolve_schedule

router = APIRouter(tags=["reminders"])


@router.get("/plan", response_model=ReminderPlanResponse)
async def get_reminder_plan(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    from_date: Annotated[date | None, Query(alias="from")] = None,
    to_date: Annotated[date | None, Query(alias="to")] = None,
) -> ReminderPlanResponse:
    """
    Get the plan of scheduled local reminders for the authenticated user.
    """
    local_today = _get_local_today(user)
    
    # Validation
    start_date = from_date if from_date is not None else local_today
    end_date = to_date if to_date is not None else start_date + timedelta(days=13)
    
    if start_date < local_today:
        raise AppError(400, "validation_error", "from cannot be before local today")
        
    if end_date < start_date:
        raise AppError(400, "validation_error", "to cannot be before from")
        
    if (end_date - start_date).days > 13:  # 14 days inclusive = max 13 difference
        raise AppError(400, "validation_error", "Maximum window is 14 days")
        
    # Query Habits and Schedules (N+1 bounded by eagerly loading schedules)
    stmt = (
        select(Habit)
        .options(selectinload(Habit.schedules))
        .where(
            Habit.user_id == user.id,
            Habit.archived_at.is_(None)
        )
    )
    result = await db.execute(stmt)
    habits = result.scalars().all()
    
    # Query non-pending occurrences in the window to suppress them
    occ_stmt = (
        select(Occurrence.habit_id, Occurrence.occurrence_date)
        .join(Habit, Occurrence.habit_id == Habit.id)
        .where(
            Habit.user_id == user.id,
            Occurrence.occurrence_date >= start_date,
            Occurrence.occurrence_date <= end_date,
            Occurrence.status != OccurrenceStatus.pending
        )
    )
    occ_result = await db.execute(occ_stmt)
    suppressed_keys = {(row.habit_id, row.occurrence_date) for row in occ_result.all()}
    
    reminders = []
    
    num_days = (end_date - start_date).days + 1
    dates_in_range = [start_date + timedelta(days=i) for i in range(num_days)]
    
    for habit in habits:
        for d in dates_in_range:
            if d < habit.start_date:
                continue
                
            schedule = resolve_schedule(habit.schedules, d)
            if not schedule:
                continue
                
            if d.weekday() not in schedule.days_of_week:
                continue
                
            if schedule.reminder_time is None:
                continue
                
            if (habit.id, d) in suppressed_keys:
                continue
                
            notification_id = f"habit:{habit.id}:{d.isoformat()}"
            
            reminders.append(
                ReminderItem(
                    notification_id=notification_id,
                    habit_id=habit.id,
                    habit_name=habit.name,
                    occurrence_date=d,
                    reminder_time=schedule.reminder_time,
                )
            )
            
    # Sort deterministically
    reminders.sort(key=lambda r: (r.occurrence_date, r.reminder_time, str(r.habit_id)))
    
    return ReminderPlanResponse(
        timezone=user.timezone,
        from_date=start_date,
        to_date=end_date,
        reminders=reminders
    )
