"""Occurrence model — Phase 4 Core Tracking Engine."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.habit import Habit


class OccurrenceStatus(enum.StrEnum):
    """Status of a daily habit occurrence."""

    pending = "pending"
    completed = "completed"
    skipped = "skipped"
    missed = "missed"


class Occurrence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "occurrences"

    habit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("habits.id", ondelete="CASCADE"),
        nullable=False,
    )
    occurrence_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    status: Mapped[OccurrenceStatus] = mapped_column(
        Enum(OccurrenceStatus, name="occurrence_status", create_constraint=True),
        nullable=False,
        default=OccurrenceStatus.pending,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    synced_from_offline: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────
    habit: Mapped[Habit] = relationship(  # noqa: F821
        back_populates="occurrences",
    )

    __table_args__ = (
        UniqueConstraint("habit_id", "occurrence_date", name="uq_occurrences_habit_date"),
        Index("ix_occurrences_habit_date", "habit_id", "occurrence_date"),
        Index(
            "ix_occurrences_pending_date",
            "occurrence_date",
            "status",
            postgresql_where="status = 'pending'",
        ),
        Index(
            "ix_occurrences_idempotency",
            "habit_id",
            "idempotency_key",
            unique=True,
            postgresql_where="idempotency_key IS NOT NULL",
        ),
    )
