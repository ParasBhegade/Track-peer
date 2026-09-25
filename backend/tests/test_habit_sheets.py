"""Tests for Habit Sheets."""

import os
import subprocess
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.api.v1.auth.check_rate_limit", new_callable=AsyncMock):
        yield



@pytest.fixture(scope="module", autouse=True)
def seed_data_fixture():
    # Run the seeder in a separate process to avoid any async event loop sharing issues
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    import sys
    subprocess.run([sys.executable, "scripts/seed_habit_sheets.py"], env=env, check=True)


async def register_and_get_token(client: AsyncClient) -> tuple[str, dict]:
    email = f"sheet_{uuid.uuid4()}@example.com"
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "strongpassword123",
            "display_name": "Sheet User",
            "timezone": "UTC",
        },
    )
    assert res.status_code == 201
    data = res.json()
    return data["tokens"]["access_token"], data["user"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── T1: Get Habit Sheets ──────────────────────────────


async def test_get_habit_sheets(client: AsyncClient):
    token, _ = await register_and_get_token(client)
    res = await client.get("/api/v1/habit-sheets", headers=auth_headers(token))
    assert res.status_code == 200
    
    data = res.json()
    assert "sheets" in data
    assert len(data["sheets"]) == 5
    
    # Verify exact categories exist
    categories = [s["category"] for s in data["sheets"]]
    assert "Study" in categories
    assert "Fitness" in categories
    
    study_sheet = next(s for s in data["sheets"] if s["category"] == "Study")
    assert len(study_sheet["habits"]) == 4


# ── T2: Create Habit from Sheet ───────────────────────


async def test_create_habit_from_sheet(client: AsyncClient):
    token, _ = await register_and_get_token(client)
    
    s_res = await client.get("/api/v1/habit-sheets", headers=auth_headers(token))
    study_sheet = next(s for s in s_res.json()["sheets"] if s["category"] == "Study")
    first_habit = study_sheet["habits"][0]
    
    res = await client.post(
        "/api/v1/habits/from-sheet",
        headers=auth_headers(token),
        json={"sheet_habit_id": first_habit["id"]},
    )
    assert res.status_code == 201
    data = res.json()
    
    assert data["name"] == first_habit["name"]
    assert data["frequency"] == first_habit["frequency"]
    assert data["schedule"]["days_of_week"] == first_habit["days_of_week"]


# ── T3: Create Habit from Sheet with Overrides ────────


async def test_create_habit_from_sheet_overrides(client: AsyncClient):
    token, _ = await register_and_get_token(client)
    
    s_res = await client.get("/api/v1/habit-sheets", headers=auth_headers(token))
    study_sheet = next(s for s in s_res.json()["sheets"] if s["category"] == "Study")
    first_habit = study_sheet["habits"][0]
    
    res = await client.post(
        "/api/v1/habits/from-sheet",
        headers=auth_headers(token),
        json={
            "sheet_habit_id": first_habit["id"],
            "overrides": {
                "days_of_week": [0, 2, 4],
                "reminder_time": "14:00"
            }
        },
    )
    assert res.status_code == 201
    data = res.json()
    
    assert data["frequency"] == "custom"  # Normalized down due to overrides
    assert data["schedule"]["days_of_week"] == [0, 2, 4]
    assert data["schedule"]["reminder_time"] == "14:00:00"
