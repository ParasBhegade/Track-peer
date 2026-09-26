"""Habit service — CRUD and schedule versioning."""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.habit import FrequencyEnum, Habit
from app.models.schedule import Schedule
from app.models.sheet import SheetHabit
from app.models.user import User
from app.schemas.habits import HabitCreate, HabitFromSheet, HabitUpdate, ScheduleUpdate


def _get_local_today(user: User) -> date:
    """Return the current local date for the user based on their timezone."""
    tz = ZoneInfo(user.timezone)
    return datetime.now(tz).date()


def _normalize_frequency(frequency: FrequencyEnum, days: list[int]) -> tuple[FrequencyEnum, list[int]]:
    """Enforce frequency rules and normalize."""
    days = sorted(list(set(days)))
    if not days:
        raise AppError(422, "validation_error", "days_of_week cannot be empty")
    for d in days:
        if d < 0 or d > 6:
            raise AppError(422, "validation_error", f"Invalid day of week: {d}")

    if frequency == FrequencyEnum.daily:
        days = [0, 1, 2, 3, 4, 5, 6]
    elif frequency == FrequencyEnum.weekdays:
        days = [0, 1, 2, 3, 4]
    else:
        # custom
        if days == [0, 1, 2, 3, 4, 5, 6]:
            frequency = FrequencyEnum.daily
        elif days == [0, 1, 2, 3, 4]:
            frequency = FrequencyEnum.weekdays

    return frequency, days


def _attach_schedules(habit: Habit, user: User) -> Habit:
    today = _get_local_today(user)
    
    # Sort schedules by effective_from DESC to be safe
    sorted_schedules = sorted(habit.schedules, key=lambda s: s.effective_from, reverse=True)
    
    # active
    past_or_present = [s for s in sorted_schedules if s.effective_from <= today]
    if past_or_present:
        habit.schedule = past_or_present[0]  # type: ignore[attr-defined]
    else:
        habit.schedule = sorted_schedules[-1] if sorted_schedules else None  # type: ignore[attr-defined]
        
    # pending
    future = sorted([s for s in sorted_schedules if s.effective_from > today], key=lambda s: s.effective_from)
    if future:
        habit.pending_schedule = future[0]  # type: ignore[attr-defined]
    else:
        habit.pending_schedule = None  # type: ignore[attr-defined]
        
    return habit


async def get_habit_or_404(db: AsyncSession, habit_id: UUID, user: User) -> Habit:
    stmt = (
        select(Habit)
        .options(selectinload(Habit.schedules))
        .where(Habit.id == habit_id)
    )
    result = await db.execute(stmt)
    habit = result.scalar_one_or_none()

    if not habit or habit.user_id != user.id:
        # 404 even if it belongs to someone else
        await db.rollback()
        raise AppError(404, "not_found", "Habit not found")

    return _attach_schedules(habit, user)


async def get_habits(db: AsyncSession, user: User, include_archived: bool) -> list[Habit]:
    stmt = select(Habit).options(selectinload(Habit.schedules)).where(Habit.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(Habit.archived_at.is_(None))
    stmt = stmt.order_by(Habit.created_at.desc())
    
    result = await db.execute(stmt)
    habits = list(result.scalars().all())
    return [_attach_schedules(h, user) for h in habits]


async def create_habit(db: AsyncSession, user: User, payload: HabitCreate) -> Habit:
    freq, days = _normalize_frequency(payload.frequency, payload.days_of_week)
    
    today = _get_local_today(user)
    start_date = payload.start_date or today
    
    if start_date < today:
        raise AppError(422, "validation_error", "start_date must be >= today")
        
    habit = Habit(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        target=payload.target,
        frequency=freq,
        start_date=start_date,
    )
    db.add(habit)
    await db.flush()  # assign ID
    
    schedule = Schedule(
        habit_id=habit.id,
        days_of_week=days,
        reminder_time=payload.reminder_time,
        effective_from=start_date,  # First schedule takes effect on start_date
    )
    db.add(schedule)
    
    from app.services.occurrence_service import generate_today_if_due
    await generate_today_if_due(db, user, habit)
    
    await db.commit()
    await db.refresh(habit, ["schedules"])
    return _attach_schedules(habit, user)


async def update_habit(db: AsyncSession, habit_id: UUID, user: User, payload: HabitUpdate) -> Habit:
    habit = await get_habit_or_404(db, habit_id, user)
    
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return habit
        
    for field, value in updates.items():
        setattr(habit, field, value)
        
    await db.commit()
    await db.refresh(habit, ["schedules"])
    return _attach_schedules(habit, user)


async def update_schedule(db: AsyncSession, habit_id: UUID, user: User, payload: ScheduleUpdate) -> Habit:
    habit = await get_habit_or_404(db, habit_id, user)
    freq, days = _normalize_frequency(payload.frequency, payload.days_of_week)
    
    today = _get_local_today(user)
    effective_from = payload.effective_from or (today + timedelta(days=1))
    
    if effective_from <= today:
        raise AppError(422, "validation_error", "effective_from must be > today")
        
    # Check if there is already a schedule starting on exactly effective_from
    # that hasn't taken effect yet (since effective_from > today, it hasn't).
    stmt = select(Schedule).where(Schedule.habit_id == habit.id, Schedule.effective_from == effective_from)
    result = await db.execute(stmt)
    existing_future = result.scalar_one_or_none()
    
    if existing_future:
        # Update in place
        existing_future.days_of_week = days
        existing_future.reminder_time = payload.reminder_time
        habit.frequency = freq
    else:
        # Insert new
        new_sched = Schedule(
            habit_id=habit.id,
            days_of_week=days,
            reminder_time=payload.reminder_time,
            effective_from=effective_from,
        )
        db.add(new_sched)
        
        # Update the habit's frequency label
        habit.frequency = freq

    # Delete stale PENDING future occurrences
    from app.services.occurrence_service import cancel_future_pending
    await cancel_future_pending(db, user, habit.id, from_date=effective_from)

    await db.commit()
    await db.refresh(habit, ["schedules"])
    return _attach_schedules(habit, user)


async def archive_habit(db: AsyncSession, habit_id: UUID, user: User) -> None:
    habit = await get_habit_or_404(db, habit_id, user)
    if habit.archived_at is None:
        # use UTC for system timestamps
        habit.archived_at = datetime.now(ZoneInfo("UTC"))
        from app.services.occurrence_service import cancel_future_pending
        await cancel_future_pending(db, user, habit.id)
        await db.commit()


async def restore_habit(db: AsyncSession, habit_id: UUID, user: User) -> Habit:
    habit = await get_habit_or_404(db, habit_id, user)
    if habit.archived_at is not None:
        habit.archived_at = None
        await db.commit()
    return _attach_schedules(habit, user)


async def create_habit_from_sheet(db: AsyncSession, user: User, payload: HabitFromSheet) -> Habit:
    stmt = select(SheetHabit).where(SheetHabit.id == payload.sheet_habit_id)
    result = await db.execute(stmt)
    sheet_habit = result.scalar_one_or_none()
    
    if not sheet_habit:
        raise AppError(404, "not_found", "Sheet habit not found")
        
    today = _get_local_today(user)
    start_date = payload.start_date or today
    if start_date < today:
        raise AppError(422, "validation_error", "start_date must be >= today")
        
    days = sheet_habit.days_of_week
    rem = sheet_habit.default_reminder_time
    freq = sheet_habit.frequency
    
    if payload.overrides:
        if payload.overrides.days_of_week is not None:
            days = payload.overrides.days_of_week
            if sorted(list(set(days))) == [0, 1, 2, 3, 4, 5, 6]:
                freq = FrequencyEnum.daily
            elif sorted(list(set(days))) == [0, 1, 2, 3, 4]:
                freq = FrequencyEnum.weekdays
            else:
                freq = FrequencyEnum.custom
        if payload.overrides.reminder_time is not None:
            rem = payload.overrides.reminder_time
            
    freq, days = _normalize_frequency(freq, days)
    
    habit = Habit(
        user_id=user.id,
        name=sheet_habit.name,
        description=sheet_habit.description,
        target=sheet_habit.target,
        frequency=freq,
        start_date=start_date,
    )
    db.add(habit)
    await db.flush()
    
    schedule = Schedule(
        habit_id=habit.id,
        days_of_week=days,
        reminder_time=rem,
        effective_from=start_date,
    )
    db.add(schedule)
    
    from app.services.occurrence_service import generate_today_if_due
    await generate_today_if_due(db, user, habit)
    
    await db.commit()
    return await get_habit_or_404(db, habit.id, user)


async def schedule_for(db: AsyncSession, habit_id: UUID, target_date: date) -> Schedule | None:
    """
    Return the schedule with the greatest effective_from <= target_date.
    If multiple exist, select the latest effective_from that is <= target_date.
    Never select a schedule with effective_from > target_date.
    Returns None if no schedule took effect by the target date.
    """
    stmt = (
        select(Schedule)
        .where(Schedule.habit_id == habit_id)
        .where(Schedule.effective_from <= target_date)
        .order_by(Schedule.effective_from.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
