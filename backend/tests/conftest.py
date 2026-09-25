"""Shared test fixtures.

Uses httpx.AsyncClient against the FastAPI app for integration testing.
Database connectivity is verified through the health endpoint and
direct session usage.
"""

from __future__ import annotations

import asyncio
import gc
import sys
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import engine
from app.main import app

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    # Patch SQLAlchemy's asyncpg adapter to NOT close connections, 
    # bypassing the asyncpg ProactorEventLoop/teardown bug on Windows.
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_connection
    
    def patched_close(self):
        self.rollback()
        # skip self.await_(self._connection.close())
        
    def patched_terminate(self):
        pass
        
    AsyncAdapt_asyncpg_connection.close = patched_close  # type: ignore[method-assign]
    AsyncAdapt_asyncpg_connection.terminate = patched_terminate  # type: ignore[method-assign]

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()



@pytest.fixture(scope="function", autouse=True)
async def function_gc():
    yield
    gc.collect()

@pytest.fixture(scope="session", autouse=True)
async def cleanup_db_engine():
    """Dispose SQLAlchemy engine pool after all tests to prevent closed event loop errors."""
    yield
    await engine.dispose()
    gc.collect()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    import asyncio
    await asyncio.sleep(0.1)
