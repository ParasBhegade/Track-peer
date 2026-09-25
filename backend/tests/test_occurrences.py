"""Tests for Phase 4 Core Tracking Engine."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.models.occurrence import Occurrence, OccurrenceStatus

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.api.v1.auth.check_rate_limit", new_callable=AsyncMock):
        yield


async def register_and_get_token(client: AsyncClient, tz: str = "UTC") -> str:
    email = f"occ_{uuid.uuid4()}@example.com"
    res_reg = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "strongpassword123", "display_name": "Occ User", "timezone": tz},
    )
    assert res_reg.status_code == 201, res_reg.text
    token = res_reg.json()["tokens"]["access_token"]
    assert isinstance(token, str)
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def token(client: AsyncClient) -> str:
    return await register_and_get_token(client)


async def test_habit_creation_generates_today(client: AsyncClient, token: str):
    """Test creating a habit generates today's occurrence if applicable."""
    today = datetime.now(ZoneInfo("UTC")).date()
    days = [today.weekday()]
    
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Today Habit",
            "frequency": "custom",
            "days_of_week": days,
            "start_date": today.isoformat(),
        },
    )
    assert res.status_code == 201
    habit_id = res.json()["id"]

    # Check today endpoint
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    assert res.status_code == 200
    data = res.json()
    
    assert data["date"] == today.isoformat()
    assert len(data["occurrences"]) == 1
    assert data["occurrences"][0]["habit_id"] == habit_id
    assert data["occurrences"][0]["status"] == "pending"
    assert data["progress"]["total"] == 1
    assert data["progress"]["completed"] == 0


async def test_idempotent_generation_and_rollover(client: AsyncClient, token: str):
    """Test generating occurrences is idempotent, and rollover marks missed."""
    # We will use the Celery task logic directly
    from sqlalchemy import select

    from app.db.session import async_session_factory
    from app.models.user import User
    from app.services.occurrence_service import rollover_and_generate_for_user
    
    today = datetime.now(ZoneInfo("UTC")).date()
    
    # Create habit
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Rollover Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
        },
    )
    assert res.status_code == 201

    # Get current user ID
    res = await client.get("/api/v1/users/me", headers=auth_headers(token))
    user_id = res.json()["id"]

    # Run generation manually (it should be idempotent)
    async with async_session_factory() as db:
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalars().first()
        assert user is not None
        await rollover_and_generate_for_user(db, user)
        await rollover_and_generate_for_user(db, user) # Second time
        await db.commit()

    # Should still only have one today
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    data = res.json()
    assert len(data["occurrences"]) == 1
    
    occ_id = data["occurrences"][0]["id"]
    
    # Simulate time passing by 1 day
    tomorrow = today + timedelta(days=1)
    
    with patch("app.services.habit_service._get_local_today", return_value=tomorrow), \
         patch("app.services.occurrence_service._get_local_today", return_value=tomorrow):
        # Run rollover again, "today" is now "tomorrow"
        async with async_session_factory() as db:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalars().first()
            assert user is not None
            await rollover_and_generate_for_user(db, user)
            await db.commit()
            
        # Check that tomorrow's occurrence is pending
        res = await client.get(f"/api/v1/occurrences?from_date={tomorrow.isoformat()}&to_date={tomorrow.isoformat()}", headers=auth_headers(token))
        occs = res.json()["occurrences"]
        assert len(occs) == 1
        assert occs[0]["status"] == "pending"
        
        # Check that yesterday's (now occ_id) became missed
        res = await client.get(f"/api/v1/occurrences?from_date={today.isoformat()}&to_date={tomorrow.isoformat()}", headers=auth_headers(token))
        occs = res.json()["occurrences"]
        assert len(occs) == 2
        missed = next(o for o in occs if o["id"] == occ_id)
        assert missed["status"] == "missed"


async def test_occurrence_updates_and_idempotency(client: AsyncClient, token: str):
    today = datetime.now(ZoneInfo("UTC")).date()
    
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={
            "name": "Update Habit",
            "frequency": "daily",
            "days_of_week": [0, 1, 2, 3, 4, 5, 6],
            "start_date": today.isoformat(),
        },
    )
    
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    occ_id = res.json()["occurrences"][0]["id"]
    
    idem_key = str(uuid.uuid4())
    headers = auth_headers(token)
    headers["Idempotency-Key"] = idem_key
    
    # pending -> completed
    res = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "completed"})
    assert res.status_code == 200
    assert res.json()["status"] == "completed"
    assert res.json()["completed_at"] is not None
    
    # Same key again -> returns same thing
    res2 = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "completed"})
    assert res2.status_code == 200
    assert res2.json() == res.json()
    
    # Same key, different status -> 409
    res3 = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "skipped"})
    assert res3.status_code == 409
    
    # New key, completed -> skipped is rejected (Phase 4 rules)
    idem_key2 = str(uuid.uuid4())
    headers["Idempotency-Key"] = idem_key2
    res4 = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "skipped"})
    assert res4.status_code == 403
    
    # New key, completed -> pending (undo)
    idem_key3 = str(uuid.uuid4())
    headers["Idempotency-Key"] = idem_key3
    res5 = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "pending"})
    assert res5.status_code == 200
    assert res5.json()["status"] == "pending"
    assert res5.json()["completed_at"] is None


async def test_missed_immutability(client: AsyncClient, token: str):
    from sqlalchemy import update

    from app.db.session import async_session_factory
    
    today = datetime.now(ZoneInfo("UTC")).date()
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Missed Habit", "frequency": "daily", "days_of_week": [0,1,2,3,4,5,6], "start_date": today.isoformat()}
    )
    
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    occ_id = res.json()["occurrences"][0]["id"]
    
    # Force to missed directly in DB
    async with async_session_factory() as db:
        await db.execute(update(Occurrence).where(Occurrence.id == occ_id).values(status=OccurrenceStatus.missed))
        await db.commit()
        
    idem_key = str(uuid.uuid4())
    headers = auth_headers(token)
    headers["Idempotency-Key"] = idem_key
    
    res = await client.put(f"/api/v1/occurrences/{occ_id}", headers=headers, json={"status": "completed"})
    assert res.status_code == 403
    assert "Missed occurrences cannot be modified" in res.json()["error"]["message"]


async def test_archive_cleans_up_future_pending(client: AsyncClient, token: str):
    today = datetime.now(ZoneInfo("UTC")).date()
    res = await client.post(
        "/api/v1/habits",
        headers=auth_headers(token),
        json={"name": "Archive Habit", "frequency": "daily", "days_of_week": [0,1,2,3,4,5,6], "start_date": today.isoformat()}
    )
    habit_id = res.json()["id"]
    
    # It generated today's pending occurrence
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    assert len(res.json()["occurrences"]) == 1
    
    # Archive
    res = await client.delete(f"/api/v1/habits/{habit_id}", headers=auth_headers(token))
    assert res.status_code == 204
    
    # Today's pending occurrence should be gone
    res = await client.get("/api/v1/today", headers=auth_headers(token))
    assert len(res.json()["occurrences"]) == 0
