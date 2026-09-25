"""Shared test fixtures.

Uses httpx.AsyncClient against the FastAPI app for integration testing.
Database connectivity is verified through the health endpoint and
direct session usage.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app


@pytest.fixture(autouse=True)
async def cleanup_db_engine():
    """Dispose SQLAlchemy engine pool after each test to prevent closed event loop errors."""
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
