"""Health endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_200(client: AsyncClient) -> None:
    """GET /api/v1/health returns 200 with expected body."""
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_response_keys(client: AsyncClient) -> None:
    """Health response contains exactly the expected keys."""
    response = await client.get("/api/v1/health")
    body = response.json()

    assert set(body.keys()) == {"status", "version"}
