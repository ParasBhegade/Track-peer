"""Tests for Habit CRUD and Schedule Versioning."""

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
            "display_name": "Habit User",
            "timezone": "UTC",
        },
    )
    assert res.status_code == 201
    data = res.json()
    return data["tokens"]["access_token"], data["user"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── T1: Habit Creation & Atomic Schedule ──────────────


async def test_create_habit(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    today = date.today().isoformat()
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Morning Run",
            "frequency": "weekdays",
            "days_of_week": [0, 1, 2, 3, 4],
            "start_date": today,
        },
    )
    assert res.status_code == 201, f"Failed: {res.text}"
    data = res.json()
    assert data["name"] == "Morning Run"
    assert data["frequency"] == "weekdays"
    assert data["start_date"] == today
    assert "schedule" in data
    assert data["schedule"]["days_of_week"] == [0, 1, 2, 3, 4]


# ── T2: Start Date in the Past (D1) ───────────────────


async def test_create_habit_past_start_date(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    fake_utc_now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=ZoneInfo("UTC"))
    class FakeDatetime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fake_utc_now.replace(tzinfo=None)
            return fake_utc_now.astimezone(tz)
            
    with patch("app.services.habit_service.datetime", FakeDatetime):
        today = fake_utc_now.date()
        past = (today - timedelta(days=1)).isoformat()
        res = await client.post(
            "/api/v1/habits",
            headers=auth_headers(token),
            json={
                "name": "Past Habit",
                "frequency": "daily",
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "start_date": past,
            },
        )
        assert res.status_code == 422


# ── T3: Frequency Normalization ───────────────────────


async def test_create_habit_frequency_normalization(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Fake Custom",
            "frequency": "custom",
            "days_of_week": [0, 1, 2, 3, 4],  # This is actually weekdays
        },
    )
    assert res.status_code == 201
    assert res.json()["frequency"] == "weekdays"


# ── T4: List / Get / Archive / Restore ────────────────


async def test_habit_lifecycle(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    # Create
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Lifecycle", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6]},
    )
    h_id = res.json()["id"]

    # List includes it
    l_res = await client.get("/api/v1/habits", headers=auth_headers(token))
    assert len(l_res.json()["habits"]) == 1

    # Archive
    d_res = await client.delete(f"/api/v1/habits/{h_id}", headers=auth_headers(token))
    assert d_res.status_code == 204

    # List (exclude archived) does not include it
    l_res2 = await client.get("/api/v1/habits", headers=auth_headers(token))
    assert len(l_res2.json()["habits"]) == 0

    # List (include archived) includes it
    l_res3 = await client.get("/api/v1/habits?include_archived=true", headers=auth_headers(token))
    assert len(l_res3.json()["habits"]) == 1

    # Restore
    r_res = await client.post(f"/api/v1/habits/{h_id}/restore", headers=auth_headers(token))
    assert r_res.status_code == 200

    # List again includes it
    l_res4 = await client.get("/api/v1/habits", headers=auth_headers(token))
    assert len(l_res4.json()["habits"]) == 1
    
    import asyncio
    await asyncio.sleep(0.1)


# ── T5: Ownership Isolation ───────────────────────────


async def test_habit_ownership_isolation(client: AsyncClient):
    token_a, _ = await register_and_get_token(client)
    token_b, _ = await register_and_get_token(client)

    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token_a),
        json={"name": "User A Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6]},
    )
    h_id = res.json()["id"]

    # User B trying to access User A's habit
    b_get = await client.get(f"/api/v1/habits/{h_id}", headers=auth_headers(token_b))
    assert b_get.status_code == 404

    b_patch = await client.patch(
        f"/api/v1/habits/{h_id}",
        headers=auth_headers(token_b),
        json={"name": "Hacked"},
    )
    assert b_patch.status_code == 404

    b_sched = await client.put(
        f"/api/v1/habits/{h_id}/schedule",
        headers=auth_headers(token_b),
        json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4]},
    )
    assert b_sched.status_code == 404

    import asyncio
    await asyncio.sleep(0.1)


# ── T6: Schedule Versioning ───────────────────────────


async def test_schedule_versioning(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    # Create habit (Schedule 1)
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "V-Habit", "frequency": "daily", "days_of_week": [0, 1, 2, 3, 4, 5, 6]},
    )
    h_id = res.json()["id"]

    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    # Update Schedule (Schedule 2 taking effect tomorrow)
    s_res = await client.put(
        f"/api/v1/habits/{h_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "weekdays", "days_of_week": [0, 1, 2, 3, 4], "effective_from": tomorrow},
    )
    assert s_res.status_code == 200
    print("DEBUG SCHEDULE RESPONSE:", s_res.json())
    assert s_res.json()["frequency"] == "weekdays"
    assert s_res.json()["pending_schedule"]["effective_from"] == tomorrow

    # Update Schedule 2 in place (since it hasn't taken effect yet)
    s_res2 = await client.put(
        f"/api/v1/habits/{h_id}/schedule",
        headers=auth_headers(token),
        json={"frequency": "custom", "days_of_week": [1, 3, 5], "effective_from": tomorrow},
    )
    assert s_res2.status_code == 200
    assert s_res2.json()["frequency"] == "custom"
