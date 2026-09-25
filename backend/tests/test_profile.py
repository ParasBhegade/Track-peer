"""Profile tests — GET/PATCH /api/v1/users/me (Step 3)."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def mock_rate_limit():
    with patch("app.api.v1.auth.check_rate_limit", new_callable=AsyncMock):
        yield


async def register_and_get_token(client: AsyncClient) -> tuple[str, dict]:
    """Register a fresh user and return (access_token, user_data)."""
    email = f"profile_{uuid.uuid4()}@example.com"
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


# ── T1: GET profile ─────────────────────────────────────


async def test_get_profile(client: AsyncClient):
    token, reg_user = await register_and_get_token(client)

    res = await client.get("/api/v1/users/me", headers=auth_headers(token))
    assert res.status_code == 200

    data = res.json()
    assert data["id"] == reg_user["id"]
    assert data["email"] == reg_user["email"]
    assert data["display_name"] == "Test User"
    assert data["timezone"] == "UTC"
    assert data["has_password"] is True
    assert data["google_linked"] is False
    assert "created_at" in data


# ── T2: GET profile unauthenticated ─────────────────────


async def test_get_profile_unauthenticated(client: AsyncClient):
    res = await client.get("/api/v1/users/me")
    assert res.status_code == 401


# ── T3: PATCH full profile ──────────────────────────────


async def test_patch_full_profile(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={
            "display_name": "Updated Name",
            "avatar_url": "https://example.com/avatar.png",
            "timezone": "America/New_York",
            "goal": "Ship the app",
        },
    )
    assert res.status_code == 200

    data = res.json()
    assert data["display_name"] == "Updated Name"
    assert data["avatar_url"] == "https://example.com/avatar.png"
    assert data["timezone"] == "America/New_York"
    assert data["goal"] == "Ship the app"


# ── T4: PATCH partial — display_name only ───────────────


async def test_patch_partial_display_name(client: AsyncClient):
    token, reg_user = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"display_name": "New Name Only"},
    )
    assert res.status_code == 200

    data = res.json()
    assert data["display_name"] == "New Name Only"
    # Other fields unchanged
    assert data["timezone"] == reg_user["timezone"]
    assert data["goal"] == reg_user["goal"]
    assert data["avatar_url"] == reg_user["avatar_url"]


# ── T5: PATCH partial — goal only ───────────────────────


async def test_patch_partial_goal(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"goal": "Become an ML Engineer"},
    )
    assert res.status_code == 200
    assert res.json()["goal"] == "Become an ML Engineer"


# ── T6: PATCH partial — timezone only ───────────────────


async def test_patch_partial_timezone(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"timezone": "America/New_York"},
    )
    assert res.status_code == 200
    assert res.json()["timezone"] == "America/New_York"


# ── T7: PATCH partial — avatar_url only ─────────────────


async def test_patch_partial_avatar_url(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"avatar_url": "https://cdn.example.com/img.jpg"},
    )
    assert res.status_code == 200
    assert res.json()["avatar_url"] == "https://cdn.example.com/img.jpg"


# ── T8: PATCH invalid timezone ──────────────────────────


async def test_patch_invalid_timezone(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"timezone": "Not/A/Timezone"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


# ── T9: PATCH display_name too long ─────────────────────


async def test_patch_display_name_too_long(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"display_name": "x" * 51},
    )
    assert res.status_code == 422


# ── T10: PATCH display_name empty ───────────────────────


async def test_patch_display_name_empty(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"display_name": ""},
    )
    assert res.status_code == 422


# ── T11: PATCH goal too long ────────────────────────────


async def test_patch_goal_too_long(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"goal": "x" * 201},
    )
    assert res.status_code == 422


# ── T12: PATCH clear optional fields to null ────────────


async def test_patch_clear_optional_fields(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    # First set them
    await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={
            "goal": "Something",
            "avatar_url": "https://example.com/img.png",
        },
    )

    # Now clear them
    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"goal": None, "avatar_url": None},
    )
    assert res.status_code == 200

    data = res.json()
    assert data["goal"] is None
    assert data["avatar_url"] is None


# ── T13: PATCH unauthenticated ──────────────────────────


async def test_patch_unauthenticated(client: AsyncClient):
    res = await client.patch(
        "/api/v1/users/me",
        json={"display_name": "Hacker"},
    )
    assert res.status_code == 401


# ── T14: PATCH protected fields rejected ────────────────


async def test_patch_protected_fields_rejected(client: AsyncClient):
    token, reg_user = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"email": "hacker@evil.com"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"

    # Verify the email was not changed
    get_res = await client.get("/api/v1/users/me", headers=auth_headers(token))
    assert get_res.json()["email"] == reg_user["email"]


# ── T15: User isolation ─────────────────────────────────


async def test_user_isolation(client: AsyncClient):
    token_a, user_a = await register_and_get_token(client)
    token_b, user_b = await register_and_get_token(client)

    # User A's token returns User A's data
    res_a = await client.get("/api/v1/users/me", headers=auth_headers(token_a))
    assert res_a.status_code == 200
    assert res_a.json()["id"] == user_a["id"]
    assert res_a.json()["id"] != user_b["id"]

    # User B's token returns User B's data
    res_b = await client.get("/api/v1/users/me", headers=auth_headers(token_b))
    assert res_b.status_code == 200
    assert res_b.json()["id"] == user_b["id"]


# ── T16: PATCH invalid avatar_url ───────────────────────


async def test_patch_invalid_avatar_url(client: AsyncClient):
    token, _ = await register_and_get_token(client)

    res = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(token),
        json={"avatar_url": "not-a-url"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
