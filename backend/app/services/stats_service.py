import calendar
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models.habit import Habit
from app.models.occurrence import Occurrence, OccurrenceStatus
from app.models.user import User
from app.schemas.stats import (
    AccountStatsResponse,
    CalendarDaySummary,
    CalendarSummaryResponse,
    HabitStatsResponse,
)
from app.services.habit_service import _get_local_today


async def get_calendar_summary(db: AsyncSession, user: User, year: int, month: int) -> CalendarSummaryResponse:
    if month < 1 or month > 12:
        raise AppError(400, "validation_error", "Invalid month")
        
    try:
        num_days = calendar.monthrange(year, month)[1]
    except ValueError:
        raise AppError(400, "validation_error", "Invalid year/month") from None
        
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)
    
    # Query occurrences grouped by date
    stmt = (
        select(
            Occurrence.occurrence_date,
            func.count(Occurrence.id).label("scheduled"),
            func.sum(
                case((Occurrence.status == OccurrenceStatus.completed, 1), else_=0)
            ).label("completed")
        )
        .join(Habit, Occurrence.habit_id == Habit.id)
        .where(
            Habit.user_id == user.id,
            Occurrence.occurrence_date >= start_date,
            Occurrence.occurrence_date <= end_date
        )
        .group_by(Occurrence.occurrence_date)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    data_map = {row.occurrence_date: {"scheduled": row.scheduled, "completed": row.completed} for row in rows}
    
    days = []
    for day_int in range(1, num_days + 1):
        d = date(year, month, day_int)
        if d in data_map:
            sch = data_map[d]["scheduled"]
            comp = data_map[d]["completed"]
            pct = int(comp / sch * 100 + 0.5) if sch > 0 else None
            days.append(CalendarDaySummary(date=d, scheduled=sch, completed=comp, percent=pct))
        else:
            days.append(CalendarDaySummary(date=d, scheduled=0, completed=0, percent=None))
            
    return CalendarSummaryResponse(days=days)


async def get_habit_stats(db: AsyncSession, user: User, habit_id: UUID) -> HabitStatsResponse:
    stmt = select(Habit).where(Habit.id == habit_id)
    habit = (await db.execute(stmt)).scalar_one_or_none()
    
    if not habit or habit.user_id != user.id:
        raise AppError(404, "not_found", "Habit not found")
        
    today = _get_local_today(user)
    
    # Weekly: Monday -> today
    monday = today - timedelta(days=today.weekday())
    
    # Monthly: 1st -> today
    first_of_month = date(today.year, today.month, 1)
    
    # Query weekly
    stmt_weekly = select(
        func.count(Occurrence.id),
        func.sum(case((Occurrence.status == OccurrenceStatus.completed, 1), else_=0))
    ).where(
        Occurrence.habit_id == habit_id,
        Occurrence.occurrence_date >= monday,
        Occurrence.occurrence_date <= today
    )
    w_sch, w_comp = (await db.execute(stmt_weekly)).one()
    w_pct = int(w_comp / w_sch * 100 + 0.5) if w_sch and w_sch > 0 else None
    
    # Query monthly
    stmt_monthly = select(
        func.count(Occurrence.id),
        func.sum(case((Occurrence.status == OccurrenceStatus.completed, 1), else_=0))
    ).where(
        Occurrence.habit_id == habit_id,
        Occurrence.occurrence_date >= first_of_month,
        Occurrence.occurrence_date <= today
    )
    m_sch, m_comp = (await db.execute(stmt_monthly)).one()
    m_pct = int(m_comp / m_sch * 100 + 0.5) if m_sch and m_sch > 0 else None
    
    return HabitStatsResponse(
        current_streak=habit.current_streak,
        longest_streak=habit.longest_streak,
        total_completions=habit.total_completions,
        weekly_completion_percent=w_pct,
        monthly_completion_percent=m_pct
    )


async def get_account_stats(db: AsyncSession, user: User) -> AccountStatsResponse:
    today = _get_local_today(user)
    monday = today - timedelta(days=today.weekday())
    
    # Active habits count & best streak
    stmt_habits = select(
        func.count(Habit.id),
        func.max(Habit.current_streak)
    ).where(
        Habit.user_id == user.id,
        Habit.archived_at.is_(None)
    )
    active_count, best_streak = (await db.execute(stmt_habits)).one()
    
    # Weekly completion for ACTIVE habits
    stmt_weekly = select(
        func.count(Occurrence.id),
        func.sum(case((Occurrence.status == OccurrenceStatus.completed, 1), else_=0))
    ).join(Habit, Occurrence.habit_id == Habit.id).where(
        Habit.user_id == user.id,
        Habit.archived_at.is_(None),
        Occurrence.occurrence_date >= monday,
        Occurrence.occurrence_date <= today
    )
    w_sch, w_comp = (await db.execute(stmt_weekly)).one()
    w_pct = int(w_comp / w_sch * 100 + 0.5) if w_sch and w_sch > 0 else None
    
    # Lifetime completions across ALL habits (including archived)
    stmt_lifetime = select(func.sum(Habit.total_completions)).where(
        Habit.user_id == user.id
    )
    lifetime = (await db.execute(stmt_lifetime)).scalar() or 0
    
    return AccountStatsResponse(
        total_active_habits=active_count or 0,
        weekly_completion_percent=w_pct,
        best_current_streak=best_streak or 0,
        total_lifetime_completions=lifetime
    )
