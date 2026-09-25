"""Profile service — GET/PATCH current user profile."""

from __future__ import annotations

from pydantic import HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UserUpdate


def get_profile(user: User) -> User:
    """Return the user as-is. Exists for layering consistency (route → service → model)."""
    return user


async def update_profile(db: AsyncSession, user: User, payload: UserUpdate) -> User:
    """Update only the fields the client actually sent.

    Protected fields cannot reach this function because UserUpdate uses
    extra="forbid" — Pydantic rejects unknown fields at the validation layer
    with a 422 before this service is ever called.
    """
    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        return user

    for field, value in updates.items():
        # Convert HttpUrl to str for DB storage (column is text)
        if isinstance(value, HttpUrl):
            value = str(value)
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user
