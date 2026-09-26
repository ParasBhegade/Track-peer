"""Occurrence service — Phase 4 Core Tracking Engine."""

from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models.habit import Habit
from app.models.occurrence import Occurrence, OccurrenceStatus
from app.models.user import User
from app.schemas.occurrences import Occurrence as OccurrenceSchema
from app.schemas.occurrences import (
    OccurrenceListResponse,
    OccurrenceUpdate,
    Progress,
    TodayResponse,
)
from app.services.habit_service import _get_local_today, schedule_for


async def generate_today_if_due(db: AsyncSession, user: User, habit: Habit) -> None:
    today = _get_local_today(user)
    if habit.archived_at is not None:
        return
    if habit.start_date > today:
        return

    schedule = await schedule_for(db, habit.id, today)
    if not schedule:
        return

    weekday = today.weekday()
    if weekday not in schedule.days_of_week:
        return

    stmt = (
        insert(Occurrence)
        .values(
            habit_id=habit.id,
            occurrence_date=today,
            status=OccurrenceStatus.pending,
        )
        .on_conflict_do_nothing(index_elements=["habit_id", "occurrence_date"])
    )
    await db.execute(stmt)


async def rollover_and_generate_for_user(db: AsyncSession, user: User) -> None:
    today = _get_local_today(user)
    yesterday = today - timedelta(days=1)

    # 1. Roll over yesterday's pending to missed
    stmt_missed = (
        update(Occurrence)
        .where(
            Occurrence.occurrence_date == yesterday,
            Occurrence.status == OccurrenceStatus.pending,
            Occurrence.habit_id.in_(
                select(Habit.id).where(Habit.user_id == user.id, Habit.archived_at.is_(None))
            ),
        )
        .values(status=OccurrenceStatus.missed)
    )
    await db.execute(stmt_missed)

    # 2. Generate today
    stmt_habits = select(Habit).where(Habit.user_id == user.id, Habit.archived_at.is_(None))
    result = await db.execute(stmt_habits)
    habits = result.scalars().all()

    for habit in habits:
        await generate_today_if_due(db, user, habit)


async def cancel_future_pending(
    db: AsyncSession, user: User, habit_id: UUID, from_date: date | None = None
) -> None:
    cutoff = from_date if from_date is not None else _get_local_today(user)
    stmt = delete(Occurrence).where(
        Occurrence.habit_id == habit_id,
        Occurrence.occurrence_date >= cutoff,
        Occurrence.status == OccurrenceStatus.pending,
    )
    await db.execute(stmt)


async def get_today(db: AsyncSession, user: User) -> TodayResponse:
    today = _get_local_today(user)

    stmt = (
        select(Occurrence)
        .options(selectinload(Occurrence.habit))
        .join(Occurrence.habit)
        .where(Habit.user_id == user.id, Occurrence.occurrence_date == today)
    )
    result = await db.execute(stmt)
    occurrences = result.scalars().all()

    schema_occurrences = []
    completed_count = 0
    total_count = 0

    for occ in occurrences:
        schedule = await schedule_for(db, occ.habit_id, today)
        rem_time = schedule.reminder_time.isoformat() if schedule and schedule.reminder_time else None

        schema_occurrences.append(
            OccurrenceSchema(
                id=occ.id,
                habit_id=occ.habit_id,
                habit_name=occ.habit.name,
                occurrence_date=occ.occurrence_date,
                status=occ.status.value,
                completed_at=occ.completed_at,
                reminder_time=rem_time,
            )
        )

        if occ.status != OccurrenceStatus.missed:
            total_count += 1
            if occ.status == OccurrenceStatus.completed:
                completed_count += 1

    percent = 0
    if total_count > 0:
        # round half up
        percent = int(completed_count / total_count * 100 + 0.5)

    return TodayResponse(
        date=today,
        occurrences=schema_occurrences,
        progress=Progress(completed=completed_count, total=total_count, percent=percent),
    )


async def get_occurrences(
    db: AsyncSession, user: User, from_date: date, to_date: date, habit_id: UUID | None = None
) -> OccurrenceListResponse:
    # Inclusive calendar days = (to_date - from_date).days + 1
    # 92 inclusive calendar days = 91 days difference
    if (to_date - from_date).days > 91:
        raise AppError(422, "validation_error", "Date range cannot exceed 92 days")

    if habit_id:
        h_result = await db.execute(select(Habit).where(Habit.id == habit_id))
        h = h_result.scalar_one_or_none()
        if not h or h.user_id != user.id:
            raise AppError(404, "not_found", "Habit not found")

    stmt = (
        select(Occurrence)
        .options(selectinload(Occurrence.habit))
        .join(Occurrence.habit)
        .where(
            Habit.user_id == user.id,
            Occurrence.occurrence_date >= from_date,
            Occurrence.occurrence_date <= to_date,
        )
    )
    if habit_id:
        stmt = stmt.where(Occurrence.habit_id == habit_id)

    result = await db.execute(stmt)
    occurrences = result.scalars().all()

    schemas = []
    for occ in occurrences:
        schedule = await schedule_for(db, occ.habit_id, occ.occurrence_date)
        rem_time = schedule.reminder_time.isoformat() if schedule and schedule.reminder_time else None

        schemas.append(
            OccurrenceSchema(
                id=occ.id,
                habit_id=occ.habit_id,
                habit_name=occ.habit.name,
                occurrence_date=occ.occurrence_date,
                status=occ.status.value,
                completed_at=occ.completed_at,
                reminder_time=rem_time,
            )
        )

    return OccurrenceListResponse(occurrences=schemas)


async def update_occurrence(
    db: AsyncSession, user: User, occurrence_id: UUID, payload: OccurrenceUpdate, idempotency_key: str
) -> OccurrenceSchema:
    today = _get_local_today(user)

    stmt = (
        select(Occurrence)
        .options(selectinload(Occurrence.habit))
        .join(Occurrence.habit)
        .where(Occurrence.id == occurrence_id, Habit.user_id == user.id)
    )
    result = await db.execute(stmt)
    occ = result.scalar_one_or_none()

    if not occ:
        raise AppError(404, "not_found", "Occurrence not found")

    if occ.occurrence_date < today:
        raise AppError(403, "forbidden", "Past occurrences are locked")
    if occ.occurrence_date > today:
        raise AppError(404, "not_found", "Occurrence not found")

    # Idempotency check
    stmt_idem = select(Occurrence).options(selectinload(Occurrence.habit)).where(
        Occurrence.habit_id == occ.habit_id, Occurrence.idempotency_key == idempotency_key
    )
    result_idem = await db.execute(stmt_idem)
    idem_occ = result_idem.scalar_one_or_none()

    if idem_occ:
        if idem_occ.id != occ.id or idem_occ.status.value != payload.status:
            raise AppError(409, "conflict", "Idempotency key already used for a different request")
        # Return previously computed response
        schedule = await schedule_for(db, idem_occ.habit_id, idem_occ.occurrence_date)
        rem_time = schedule.reminder_time.isoformat() if schedule and schedule.reminder_time else None
        return OccurrenceSchema(
            id=idem_occ.id,
            habit_id=idem_occ.habit_id,
            habit_name=idem_occ.habit.name,
            occurrence_date=idem_occ.occurrence_date,
            status=idem_occ.status.value,
            completed_at=idem_occ.completed_at,
            reminder_time=rem_time,
        )

    # Status transition validation
    if occ.status == OccurrenceStatus.missed:
        raise AppError(403, "forbidden", "Missed occurrences cannot be modified")

    if occ.status == OccurrenceStatus.completed and payload.status == "skipped":
        raise AppError(403, "forbidden", "Cannot transition directly from completed to skipped")
    if occ.status == OccurrenceStatus.skipped and payload.status == "completed":
        raise AppError(403, "forbidden", "Cannot transition directly from skipped to completed")

    # Apply mutation
    occ.status = OccurrenceStatus(payload.status)
    if occ.status == OccurrenceStatus.completed:
        occ.completed_at = datetime.now(ZoneInfo("UTC"))
    else:
        occ.completed_at = None

    occ.idempotency_key = idempotency_key

    from app.services.streak_service import recalculate_habit_aggregates
    await recalculate_habit_aggregates(db, occ.habit_id, user)

    await db.commit()

    schedule = await schedule_for(db, occ.habit_id, occ.occurrence_date)
    rem_time = schedule.reminder_time.isoformat() if schedule and schedule.reminder_time else None

    return OccurrenceSchema(
        id=occ.id,
        habit_id=occ.habit_id,
        habit_name=occ.habit.name,
        occurrence_date=occ.occurrence_date,
        status=occ.status.value,
        completed_at=occ.completed_at,
        reminder_time=rem_time,
    )
