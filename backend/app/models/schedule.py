"""Schedule model — Phase 2 §2, Phase 3 §0 Gap #6, §5.

Design note (Phase 2):
  Editing a schedule inserts a new row with a new effective_from (>= tomorrow)
  rather than mutating an in-effect row. A row not yet in effect (same
  effective_from) may be updated in place. Occurrence generation always uses
  the schedule effective on that occurrence's date.
"""

from __future__ import annotations

import uuid
from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.habit import Habit


class Schedule(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "schedules"

    habit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("habits.id", ondelete="CASCADE"),
        nullable=False,
    )
    days_of_week: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
        comment="0=Mon..6=Sun",
    )
    reminder_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="user-local date; edits create a new row (must be >= tomorrow)",
    )

    # ── Relationships ────────────────────────────────────
    habit: Mapped[Habit] = relationship(  # noqa: F821
        back_populates="schedules",
    )

    __table_args__ = (
        # Unique constraint: one schedule per habit per effective_from date
        UniqueConstraint("habit_id", "effective_from", name="uq_schedules_habit_effective"),
        # Check: days_of_week must have 1–7 elements
        CheckConstraint(
            text("cardinality(days_of_week) BETWEEN 1 AND 7"),
            name="ck_schedules_days_count",
        ),
        # Index for "which schedule applies on date D" query (Phase 2 §3)
        Index("ix_schedules_habit_effective_desc", "habit_id", effective_from.desc()),
    )
