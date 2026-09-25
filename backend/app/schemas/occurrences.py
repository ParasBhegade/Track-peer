"""Occurrence schemas — Phase 4 Core Tracking Engine."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class OccurrenceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Occurrence(OccurrenceBase):
    id: UUID
    habit_id: UUID
    habit_name: str
    occurrence_date: date
    status: Literal["pending", "completed", "skipped", "missed"]
    completed_at: datetime | None = None
    reminder_time: str | None = None


class Progress(BaseModel):
    completed: int
    total: int
    percent: int


class TodayResponse(BaseModel):
    date: date
    occurrences: list[Occurrence]
    progress: Progress


class OccurrenceListResponse(BaseModel):
    occurrences: list[Occurrence]


class OccurrenceUpdate(BaseModel):
    status: Literal["completed", "skipped", "pending"]
    model_config = ConfigDict(extra="forbid")
