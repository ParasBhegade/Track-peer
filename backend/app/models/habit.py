"""Habit model — Phase 2 §2, Phase 3 §0 Gaps #2/#7/#8, §5."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.schedule import Schedule
    from app.models.user import User


class FrequencyEnum(enum.StrEnum):
    """Habit frequency label — derived from schedules.days_of_week."""

    daily = "daily"
    weekdays = "weekdays"
    custom = "custom"


class Habit(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "habits"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    target: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment='optional target, e.g. "1 problem/day" (FR-3.1)',
    )
    frequency: Mapped[FrequencyEnum] = mapped_column(
        Enum(FrequencyEnum, name="habit_frequency", create_constraint=True),
        nullable=False,
        comment="derived label — schedules.days_of_week is the source of truth",
    )
    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="must be >= today in user timezone at creation",
    )
    is_shared_habit: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="true if cloned from a challenge template",
    )
    # Plain UUID — no FK constraint yet (Phase 3 §0 Gap #7).
    # FK added in the challenges migration to avoid circular dependency.
    source_challenge_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        comment="set only if is_shared_habit; FK added in challenges migration",
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="soft delete",
    )

    # ── Relationships ────────────────────────────────────
    user: Mapped[User] = relationship(  # noqa: F821
        back_populates="habits",
    )
    schedules: Mapped[list[Schedule]] = relationship(  # noqa: F821
        back_populates="habit",
        lazy="selectin",
        order_by="Schedule.effective_from.desc()",
    )

    __table_args__ = (
        # Partial index: active habits per user (Phase 2 §3 scalability checklist)
        Index("ix_habits_user_id_active", "user_id", postgresql_where="archived_at IS NULL"),
    )
