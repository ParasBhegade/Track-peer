"""User model — Phase 2 §2, Phase 3 §0 Gap #1, §5."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.habit import Habit


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        comment="null if OAuth-only account",
    )
    google_oauth_id: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        unique=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="IANA tz name, e.g. Asia/Kolkata",
    )
    display_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    goal: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="doubles as profile bio",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="URL only in MVP; upload flow deferred (FR-2.1)",
    )

    # ── Relationships (loaded lazily) ────────────────────
    habits: Mapped[list[Habit]] = relationship(  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )

    __table_args__ = (
        # Unique index on lowercased email (Phase 3 §5)
        Index("ix_users_email_lower", func.lower(email), unique=True),
    )

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None

    @property
    def google_linked(self) -> bool:
        return self.google_oauth_id is not None
