from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.habit import Habit
from app.models.occurrence import Occurrence, OccurrenceStatus
from app.models.schedule import Schedule
from app.models.user import User
from app.services.habit_service import _get_local_today


async def recalculate_habit_aggregates(db: AsyncSession, habit_id: UUID, user: User) -> None:
    """
    Recalculates current_streak, longest_streak, and total_completions from
    authoritative occurrence history. Updates the habit in the current transaction.
    """
    today = _get_local_today(user)

    # 1. Fetch habit with schedules
    stmt_habit = select(Habit).options(selectinload(Habit.schedules)).where(Habit.id == habit_id)
    habit = (await db.execute(stmt_habit)).scalar_one_or_none()
    if not habit:
        return

    # 2. Total completions
    stmt_total = select(func.count(Occurrence.id)).where(
        Occurrence.habit_id == habit_id,
        Occurrence.status == OccurrenceStatus.completed
    )
    total_completions = (await db.execute(stmt_total)).scalar_one() or 0

    # 3. Fetch all occurrences for this habit (indexed by date)
    # We use paginated fetching by querying the occurrences table directly.
    # Since occurrences are only generated for scheduled days, the occurrences table
    # effectively IS the scheduled-occurrence history. However, to respect the
    # "schedule-version-aware historical traversal", we must ensure we only consider
    # occurrences that were actually scheduled according to the schedule versions,
    # OR we just rely on the fact that occurrences were generated using those schedules.
    # To strictly follow "while scheduled occurrence exists: occurrence = occurrence for date",
    # we can iterate scheduled dates backward.
    
    schedules = sorted(habit.schedules, key=lambda s: s.effective_from, reverse=True)
    
    def get_applicable_schedule(d: date) -> Schedule | None:
        for s in schedules:
            if s.effective_from <= d:
                return s
        return None

    # Generate scheduled dates backward from today down to start_date
    scheduled_dates = []
    curr = today
    while curr >= habit.start_date:
        sched = get_applicable_schedule(curr)
        if sched and curr.weekday() in sched.days_of_week:
            scheduled_dates.append(curr)
        curr -= timedelta(days=1)

    # Fetch all occurrences for this habit, indexed by date.
    # To do this in pages:
    page_size = 50
    current_streak = 0
    longest_streak = 0
    current_broken = False
    
    current_run = 0

    for i in range(0, len(scheduled_dates), page_size):
        page_dates = scheduled_dates[i:i+page_size]
        
        stmt_occ = select(Occurrence).where(
            Occurrence.habit_id == habit_id,
            Occurrence.occurrence_date.in_(page_dates)
        )
        occurrences = (await db.execute(stmt_occ)).scalars().all()
        occ_map = {o.occurrence_date: o for o in occurrences}
        
        for d in page_dates:
            occ = occ_map.get(d)
            
            if occ and occ.status == OccurrenceStatus.completed:
                if not current_broken:
                    current_streak += 1
                current_run += 1
                if current_run > longest_streak:
                    longest_streak = current_run
            elif occ and occ.status == OccurrenceStatus.pending and d == today:
                # Today is still open. Does not break the streak, does not add to it.
                continue
            elif occ and occ.status == OccurrenceStatus.skipped:
                # Skipped does not break the streak, does not add to it.
                continue
            else:
                # SKIPPED, MISSED, or missing occurrence (which means not completed)
                current_broken = True
                current_run = 0

    habit.current_streak = current_streak
    habit.longest_streak = longest_streak
    habit.total_completions = total_completions
