"""Async SQLAlchemy engine and session factory.

Uses asyncpg as the PostgreSQL driver (Phase 3 §7.2, Decision D5).
"""

from __future__ import annotations

import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import settings

is_testing = settings.APP_ENV == "testing" or "pytest" in sys.modules

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=StaticPool if is_testing else None,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
