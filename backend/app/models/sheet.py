"""Habit sheet models — Phase 2 §2, Phase 3 §0 Gap #3, §5.

Preloaded templates. Adding a habit from a sheet copies the template
into a normal habits + schedules row; the user's habit is independent
of the sheet afterwards.
"""

from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import Enum, ForeignKey, Integer, Text, Time
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.habit import FrequencyEnum


class HabitSheet(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "habit_sheets"

    slug: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Fitness, Study, Productivity, Health, Reading (FR-3.2)",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────
    habits: Mapped[list[SheetHabit]] = relationship(
        back_populates="sheet",
        lazy="selectin",
        order_by="SheetHabit.sort_order",
        cascade="all, delete-orphan",
    )


class SheetHabit(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "sheet_habits"

    sheet_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("habit_sheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    frequency: Mapped[FrequencyEnum] = mapped_column(
        Enum(FrequencyEnum, name="habit_frequency", create_constraint=False, create_type=False),
        nullable=False,
    )
    days_of_week: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        nullable=False,
    )
    default_reminder_time: Mapped[time | None] = mapped_column(
        Time,
        nullable=True,
    )
    target: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────
    sheet: Mapped[HabitSheet] = relationship(
        back_populates="habits",
    )
