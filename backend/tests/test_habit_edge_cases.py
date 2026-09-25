"""Tests for Habit CRUD edge cases and timezone logic."""

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.deps import get_db
from app.db.session import async_session_factory
from app.main import app
from app.models.habit import Habit
from app.models.schedule import Schedule
from app.services.habit_service import schedule_for

pytestmark = pytest.mark.asyncio

@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.api.v1.auth.check_rate_limit", new_callable=AsyncMock):
        yield

async def register_and_get_token(client: AsyncClient, tz: str = "UTC") -> tuple[str, dict]:
    email = f"edge_{uuid.uuid4()}@example.com"
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "display_name": "Edge User",
            "timezone": tz,
        },
    )
    assert res.status_code == 201
    data = res.json()
    return data["tokens"]["access_token"], data["user"]

def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}

# ── 1. schedule_for() BOUNDARY TESTS ──────────────────────────

async def test_schedule_for_boundaries(client: AsyncClient):
    token, user = await register_and_get_token(client)
    
    today = date.today()
    today_str = today.isoformat()
    # A. Create initial schedule (effective_from = today)
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Boundary Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": today_str},
    )
    assert res.status_code == 201
    habit_id = res.json()["id"]

    tomorrow = today + timedelta(days=1)
    tomorrow_str = tomorrow.isoformat()
    # Create future schedule (effective_from = tomorrow)
    s_res = await client.put(
        f"/api/v1/habits/{habit_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": tomorrow_str},
    )
    assert s_res.status_code == 200

    async with async_session_factory() as db:
        h_id = uuid.UUID(habit_id)
        # Target date BEFORE schedule change (today) -> should get old schedule
        sched_before = await schedule_for(db, h_id, today)
        assert sched_before is not None
        assert sched_before.days_of_week == [0, 1, 2, 3, 4, 5, 6]
        
        # Target date EXACTLY ON effective_from (tomorrow) -> should get new schedule
        sched_on = await schedule_for(db, h_id, tomorrow)
        assert sched_on is not None
        assert sched_on.days_of_week == [0, 1, 2, 3, 4]
        
        # Target date AFTER effective_from (tomorrow + 1) -> should get new schedule
        sched_after = await schedule_for(db, h_id, tomorrow + timedelta(days=1))
        assert sched_after is not None
        assert sched_after.days_of_week == [0, 1, 2, 3, 4]
        
        # Future schedule must not affect earlier target dates
        yesterday = today - timedelta(days=1)
        sched_earlier = await schedule_for(db, h_id, yesterday)
        assert sched_earlier is None # Start date was today, so nothing is active yesterday

# ── 2. HISTORICAL SCHEDULE IMMUTABILITY ──────────────────────

async def test_historical_schedule_immutability(client: AsyncClient):
    token, user = await register_and_get_token(client)
    
    today_str = date.today().isoformat()
    # Create habit
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Immutable Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": today_str},
    )
    assert res.status_code == 201
    habit_id = res.json()["id"]
    
    async with async_session_factory() as db:
        # Capture original historical schedule fields directly from DB
        h_id = uuid.UUID(habit_id)
        result = await db.execute(select(Schedule).where(Schedule.habit_id == h_id))
        schedules_before = result.scalars().all()
        assert len(schedules_before) == 1
        historical_id = schedules_before[0].id
        historical_freq = schedules_before[0].days_of_week
        historical_eff = schedules_before[0].effective_from
        
    # Perform a future schedule update
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    s_res = await client.put(
        f"/api/v1/habits/{habit_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": tomorrow_str},
    )
    assert s_res.status_code == 200
    
    # Reload historical schedule directly from the database
    async with async_session_factory() as db:
        result = await db.execute(select(Schedule).where(Schedule.id == historical_id))
        historical_schedule = result.scalar_one_or_none()
        
        assert historical_schedule is not None
        assert historical_schedule.days_of_week == historical_freq
        assert historical_schedule.effective_from == historical_eff

# ── 3. pending_schedule TESTS ────────────────────────────────

async def test_pending_schedule_resolution(client: AsyncClient):
    token, user = await register_and_get_token(client)
    
    today_str = date.today().isoformat()
    # A. No future schedule -> pending_schedule is null
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Pending Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": today_str},
    )
    assert res.status_code == 201
    habit_id = res.json()["id"]
    assert res.json()["pending_schedule"] is None
    
    # B. One future schedule -> that schedule is returned
    d1_str = (date.today() + timedelta(days=1)).isoformat()
    s1_res = await client.put(
        f"/api/v1/habits/{habit_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": d1_str},
    )
    assert s1_res.status_code == 200
    assert s1_res.json()["pending_schedule"]["effective_from"] == d1_str
    
    # C. Multiple future schedules -> EARLIEST future schedule is returned
    d3_str = (date.today() + timedelta(days=3)).isoformat()
    s3_res = await client.put(
        f"/api/v1/habits/{habit_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "custom", "days_of_week": [1, 3], "effective_from": d3_str},
    )
    assert s3_res.status_code == 200
    assert s3_res.json()["pending_schedule"]["effective_from"] == d1_str  # D1 is earlier than D3

# ── 4. USER TIMEZONE D1/D2 TESTS ─────────────────────────────

async def test_user_timezone_boundaries(client: AsyncClient):
    # Use timezone +14 (Pacific/Kiritimati)
    # If UTC is 2026-01-01 11:00, +14 is 2026-01-02 01:00.
    # Local today is 01-02, UTC today is 01-01.
    token, user = await register_and_get_token(client, tz="Pacific/Kiritimati")
    
    fake_utc_now = datetime(2026, 1, 1, 11, 0, 0, tzinfo=ZoneInfo("UTC"))
    
    class FakeDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fake_utc_now.replace(tzinfo=None)
            return fake_utc_now.astimezone(tz)
            
    with patch("app.services.habit_service.datetime", FakeDatetime):
        # D1: start_date >= user's local today (2026-01-02)
        
        # Test 1: Start date = 2026-01-01 (UTC today, but local yesterday) => Should fail!
        res_fail = await client.post(
            "/api/v1/habits",
            headers=auth_headers(token),
            json={"name": "Tz Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": "2026-01-01"},
        )
        assert res_fail.status_code == 422
        
        # Test 2: Start date = 2026-01-02 (Local today) => Should succeed!
        res_ok = await client.post(
            "/api/v1/habits",
            headers=auth_headers(token),
            json={"name": "Tz Habit 2", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": "2026-01-02"},
        )
        assert res_ok.status_code == 201
        habit_id = res_ok.json()["id"]
        
        # D2: effective_from > user's local today (2026-01-02)
        
        # Test 3: Update schedule with effective_from = 2026-01-02 (Local today) => Should fail!
        s_res_fail = await client.put(
            f"/api/v1/habits/{habit_id}/schedule",
            headers=auth_headers(token),
            json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": "2026-01-02"},
        )
        assert s_res_fail.status_code == 422
        
        # Test 4: Update schedule with effective_from = 2026-01-03 (Local tomorrow) => Should succeed!
        s_res_ok = await client.put(
            f"/api/v1/habits/{habit_id}/schedule",
            headers=auth_headers(token),
            json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": "2026-01-03"},
        )
        assert s_res_ok.status_code == 200

# ── 5. ATOMIC HABIT + FIRST SCHEDULE ROLLBACK ────────────────

async def test_atomic_habit_schedule_rollback(client: AsyncClient):
    token, user = await register_and_get_token(client)
    today_str = date.today().isoformat()
    
    async def override_get_db():
        async with async_session_factory() as session:
            original_add = session.add
            def fake_add(instance, *args, **kwargs):
                if isinstance(instance, Schedule):
                    raise Exception("Forced schedule creation failure")
                return original_add(instance, *args, **kwargs)
            session.add = fake_add
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        res = await client.post(
            "/api/v1/habits",
            headers=auth_headers(token),
            json={"name": "Rollback Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": today_str},
        )
        assert res.status_code == 500
    except Exception as e:
        assert "Forced schedule creation failure" in str(e)
    finally:
        app.dependency_overrides.pop(get_db, None)
        
    # Verify transaction rolled back (no orphan habit exists)
    async with async_session_factory() as db:
        result = await db.execute(select(Habit).where(Habit.name == "Rollback Habit"))
        habit = result.scalar_one_or_none()
        assert habit is None, "Orphan habit was found! Transaction did not roll back properly."

# ── 6. SCHEDULE UPDATE ROLLBACK ──────────────────────────────

async def test_schedule_update_rollback(client: AsyncClient):
    token, user = await register_and_get_token(client)
    today_str = date.today().isoformat()
    
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Update Rollback Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6], "start_date": today_str},
    )
    assert res.status_code == 201
    habit_id = res.json()["id"]
    
    tomorrow_str = (date.today() + timedelta(days=1)).isoformat()
    
    async def override_get_db():
        async with async_session_factory() as session:
            original_add = session.add
            def fake_add(instance, *args, **kwargs):
                if isinstance(instance, Schedule):
                    raise Exception("Forced schedule update failure")
                return original_add(instance, *args, **kwargs)
            session.add = fake_add
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        s_res = await client.put(
            f"/api/v1/habits/{habit_id}/schedule",
            headers=auth_headers(token),
            json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": tomorrow_str},
        )
        assert s_res.status_code == 500
    except Exception as e:
        assert "Forced schedule update failure" in str(e)
    finally:
        app.dependency_overrides.pop(get_db, None)
        
    # Verify the original schedule remains unchanged and no partial state exists
    async with async_session_factory() as db:
        h_id = uuid.UUID(habit_id)
        result = await db.execute(select(Schedule).where(Schedule.habit_id == h_id))
        schedules = result.scalars().all()
        assert len(schedules) == 1
        assert schedules[0].days_of_week == [0, 1, 2, 3, 4, 5, 6]
        assert schedules[0].effective_from == date.today()
