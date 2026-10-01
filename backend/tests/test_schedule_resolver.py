import uuid
from datetime import date

from app.models.schedule import Schedule
from app.services.habit_service import resolve_schedule


def create_schedule(effective_from: date) -> Schedule:
    return Schedule(
        id=uuid.uuid4(),
        habit_id=uuid.uuid4(),
        days_of_week=[0, 1, 2, 3, 4, 5, 6],
        effective_from=effective_from,
    )

def test_resolve_schedule_no_applicable():
    """When all schedules are in the future, return None."""
    s1 = create_schedule(date(2026, 1, 5))
    s2 = create_schedule(date(2026, 1, 10))
    schedules = [s1, s2]
    
    # Target date before any schedule
    result = resolve_schedule(schedules, date(2026, 1, 1))
    assert result is None

def test_resolve_schedule_exact_boundary():
    """When target_date exactly matches a schedule's effective_from, it should be selected."""
    s1 = create_schedule(date(2026, 1, 5))
    s2 = create_schedule(date(2026, 1, 10))
    schedules = [s1, s2]
    
    # Target date exactly matches s1
    result = resolve_schedule(schedules, date(2026, 1, 5))
    assert result == s1
    
    # Target date exactly matches s2
    result = resolve_schedule(schedules, date(2026, 1, 10))
    assert result == s2

def test_resolve_schedule_historical_and_current_and_future():
    """
    Given historical, current, and future schedules,
    resolve_schedule should pick the latest one <= target_date.
    """
    s_historical = create_schedule(date(2025, 1, 1))
    s_current = create_schedule(date(2026, 1, 1))
    s_future = create_schedule(date(2027, 1, 1))
    schedules = [s_historical, s_current, s_future]
    
    # S_historical
    assert resolve_schedule(schedules, date(2025, 6, 1)) == s_historical
    
    # S_current
    assert resolve_schedule(schedules, date(2026, 6, 1)) == s_current
    
def test_resolve_schedule_multiple_versions():
    """
    When multiple past versions exist, the latest applicable version wins.
    """
    s1 = create_schedule(date(2026, 1, 1))
    s2 = create_schedule(date(2026, 1, 15))
    s3 = create_schedule(date(2026, 2, 1))
    
    # Disordered array
    schedules = [s2, s3, s1]
    
    # Target is 2026-01-20 -> latest applicable is s2 (2026-01-15)
    assert resolve_schedule(schedules, date(2026, 1, 20)) == s2
    
    # Target is 2026-03-01 -> latest applicable is s3 (2026-02-01)
    assert resolve_schedule(schedules, date(2026, 3, 1)) == s3
