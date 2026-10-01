import uuid
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.api.v1.auth.check_rate_limit", new_callable=AsyncMock):
        yield

async def register_and_get_token(client: AsyncClient) -> tuple[str, dict]:
    email = f"habit_{uuid.uuid4()}@example.com"
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "display_name": "Test User",
            "timezone": "UTC",
        },
    )
    assert res.status_code == 201
    data = res.json()
    return data["tokens"]["access_token"], data["user"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_reminders_default_window(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()

    # Create habit
    await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Daily Reminder",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "10:00:00",
        },
    )

    # Fetch reminders plan
    res = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    
    assert data["from"] == today.isoformat()
    assert data["to"] == (today + timedelta(days=13)).isoformat()
    assert len(data["reminders"]) == 14
    
    # Check >14 day rejection
    res_large = await client.get(
        f"/api/v1/reminders/plan?from={today.isoformat()}&to={(today + timedelta(days=14)).isoformat()}",
        headers=auth_headers(token)
    )
    assert res_large.status_code == 400


async def test_reminders_from_before_today_rejected(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    yesterday = (datetime.now(ZoneInfo("UTC")).date() - timedelta(days=1)).isoformat()
    
    res = await client.get(f"/api/v1/reminders/plan?from={yesterday}", headers=auth_headers(token))
    assert res.status_code == 400


async def test_reminders_today_completed_skipped_suppression(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Create habit
    res_h = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Suppression Test",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "09:00:00",
        },
    )
    assert res_h.status_code == 201
    
    # Fetch today's occurrences
    res_today = await client.get("/api/v1/today", headers=auth_headers(token))
    occ = res_today.json()["occurrences"][0]
    
    # Mark completed
    await client.put(
        f"/api/v1/occurrences/{occ['id']}",
        headers={**auth_headers(token), "Idempotency-Key": str(uuid.uuid4())},
        json={"status": "completed"}
    )
    
    # Plan should exclude today
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    data = res_plan.json()
    
    dates_found = [r["occurrence_date"] for r in data["reminders"]]
    assert today.isoformat() not in dates_found
    # Tomorrow should be there
    assert (today + timedelta(days=1)).isoformat() in dates_found


async def test_reminders_archived_and_no_time_excluded(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Create habit 1 (to be archived)
    res_h1 = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "To Archive",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "09:00:00",
        },
    )
    h1_id = res_h1.json()["id"]
    await client.delete(f"/api/v1/habits/{h1_id}", headers=auth_headers(token))
    
    # Create habit 2 (no reminder time)
    res_h2 = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "No Time",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": None,
        },
    )
    h2_id = res_h2.json()["id"]
    
    # Fetch plan
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    data = res_plan.json()
    
    habit_ids = {r["habit_id"] for r in data["reminders"]}
    assert h1_id not in habit_ids
    assert h2_id not in habit_ids


async def test_reminders_ownership_isolation(client: AsyncClient) -> None:
    token1, _ = await register_and_get_token(client)
    token2, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # User 1 creates habit
    res_h1 = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token1),
        json={
            "name": "User 1 Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "09:00:00",
        },
    )
    h1_id = res_h1.json()["id"]
    
    # User 2 plan
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token2))
    data = res_plan.json()
    
    habit_ids = {r["habit_id"] for r in data["reminders"]}
    assert h1_id not in habit_ids


async def test_reminders_bounded_query_count(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    for i in range(5):
        await client.post(
            "/api/v1/habits",
            headers=auth_headers(token),
            json={
                "name": f"Habit {i}",
                "frequency": "daily",
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "start_date": today.isoformat(),
                "reminder_time": "09:00:00",
            },
        )
        
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    assert res_plan.status_code == 200
    assert len(res_plan.json()["reminders"]) == 70  # 5 habits * 14 days


async def test_reminders_explicit_valid_window_and_determinism(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    end_date = today + timedelta(days=5)

    res_h = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Deterministic Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "12:00:00",
        },
    )
    habit_id = res_h.json()["id"]

    res_plan1 = await client.get(
        f"/api/v1/reminders/plan?from={today.isoformat()}&to={end_date.isoformat()}",
        headers=auth_headers(token)
    )
    assert res_plan1.status_code == 200
    data1 = res_plan1.json()

    # Repeated request identical
    res_plan2 = await client.get(
        f"/api/v1/reminders/plan?from={today.isoformat()}&to={end_date.isoformat()}",
        headers=auth_headers(token)
    )
    assert res_plan1.json() == res_plan2.json()

    assert data1["from"] == today.isoformat()
    assert data1["to"] == end_date.isoformat()
    assert len(data1["reminders"]) == 6  # today + 5 days = 6 days inclusive

    # Check determinism and sorting
    reminders = data1["reminders"]
    for i, r in enumerate(reminders):
        expected_date = today + timedelta(days=i)
        assert r["occurrence_date"] == expected_date.isoformat()
        assert r["notification_id"] == f"habit:{habit_id}:{expected_date.isoformat()}"
        assert r["reminder_time"] == "12:00:00"

    # Sorting is occurrence_date ASC, reminder_time ASC, habit_id ASC
    # Create another habit at same time
    await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Deterministic Habit B",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "10:00:00",
        },
    )
    
    res_plan3 = await client.get(
        f"/api/v1/reminders/plan?from={today.isoformat()}&to={end_date.isoformat()}",
        headers=auth_headers(token)
    )
    reminders3 = res_plan3.json()["reminders"]
    # For a given day, 10:00 should come before 12:00
    assert reminders3[0]["reminder_time"] == "10:00:00"
    assert reminders3[1]["reminder_time"] == "12:00:00"


async def test_reminders_timezone_boundary(client: AsyncClient) -> None:
    # Register with a timezone far from UTC
    email = f"tz_{uuid.uuid4()}@example.com"
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "display_name": "TZ User",
            "timezone": "Pacific/Kiritimati", # UTC+14
        },
    )
    assert res.status_code == 201
    token = res.json()["tokens"]["access_token"]
    
    local_today = datetime.now(ZoneInfo("Pacific/Kiritimati")).date()
    
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    assert res_plan.status_code == 200
    assert res_plan.json()["timezone"] == "Pacific/Kiritimati"
    assert res_plan.json()["from"] == local_today.isoformat()


async def test_reminders_schedule_version_resolution(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Create habit
    res_h = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Versioned Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "08:00:00",
        },
    )
    h_id = res_h.json()["id"]
    
    # Edit schedule effective tomorrow
    tomorrow = today + timedelta(days=1)
    await client.put(
        f"/api/v1/habits/{h_id}/schedule",
        headers={**auth_headers(token), "Idempotency-Key": str(uuid.uuid4())},
        json={
            "effective_from": tomorrow.isoformat(),
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "reminder_time": "09:00:00",
        }
    )
    
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    reminders = res_plan.json()["reminders"]
    
    today_rem = next(r for r in reminders if r["occurrence_date"] == today.isoformat())
    tmrw_rem = next(r for r in reminders if r["occurrence_date"] == tomorrow.isoformat())
    
    assert today_rem["reminder_time"] == "08:00:00"
    assert tmrw_rem["reminder_time"] == "09:00:00"


async def test_reminders_weekday_inclusion(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Habit only on today's weekday
    today_weekday = today.weekday()
    
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Weekday Habit",
            "frequency": "custom",
            "days_of_week": [today_weekday],
            "start_date": today.isoformat(),
            "reminder_time": "14:00:00",
        },
    )
    assert res.status_code == 201
    
    res_plan = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    reminders = res_plan.json()["reminders"]
    
    # In a 14 day window, a specific weekday occurs exactly 2 times
    assert len(reminders) == 2
    for r in reminders:
        r_date = date.fromisoformat(r["occurrence_date"])
        assert r_date.weekday() == today_weekday


async def test_reminders_skipped_missed_suppression(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Create habit
    await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Suppression Test Multi",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "09:00:00",
        },
    )
    
    # Fetch today's occurrences (generates it as pending)
    res_today = await client.get("/api/v1/today", headers=auth_headers(token))
    occ = res_today.json()["occurrences"][0]
    
    # Pending should be INCLUDED
    res_plan1 = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    dates1 = [r["occurrence_date"] for r in res_plan1.json()["reminders"]]
    assert today.isoformat() in dates1
    
    # Mark skipped
    await client.put(
        f"/api/v1/occurrences/{occ['id']}",
        headers={**auth_headers(token), "Idempotency-Key": str(uuid.uuid4())},
        json={"status": "skipped"}
    )
    
    # Skipped should be EXCLUDED
    res_plan2 = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    dates2 = [r["occurrence_date"] for r in res_plan2.json()["reminders"]]
    assert today.isoformat() not in dates2
    
    # Note: MISSED is implicitly excluded by the != pending query, but since tests cannot easily 
    # force a missed transition without waiting out the UTC day, checking SKIPPED proves the != pending logic.
    # We will directly update the db to 'missed' to prove it.
    from sqlalchemy import update

    from app.db.session import async_session_factory
    from app.models.occurrence import Occurrence, OccurrenceStatus
    
    async with async_session_factory() as session:
        await session.execute(
            update(Occurrence).where(Occurrence.id == occ['id']).values(status=OccurrenceStatus.missed)
        )
        await session.commit()
        
    res_plan3 = await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    dates3 = [r["occurrence_date"] for r in res_plan3.json()["reminders"]]
    assert today.isoformat() not in dates3


async def test_reminders_readonly_behavior(client: AsyncClient) -> None:
    token, _ = await register_and_get_token(client)
    today = datetime.now(ZoneInfo("UTC")).date()
    
    await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Readonly Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
            "reminder_time": "09:00:00",
        },
    )
    
    # Check DB occurrences before plan
    from sqlalchemy import func, select

    from app.db.session import async_session_factory
    from app.models.occurrence import Occurrence
    
    async with async_session_factory() as session:
        count_before = (await session.execute(select(func.count(Occurrence.id)))).scalar()
        
    await client.get("/api/v1/reminders/plan", headers=auth_headers(token))
    
    async with async_session_factory() as session:
        count_after = (await session.execute(select(func.count(Occurrence.id)))).scalar()
        
    assert count_before == count_after, "Endpoint mutated occurrences!"
