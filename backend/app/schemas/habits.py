"""Schemas for Habits and Habit Sheets."""

from datetime import date, datetime, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.habit import FrequencyEnum


class DaysOfWeek(BaseModel):
    # We use a custom type/validator logic for list[int]
    pass


class ScheduleView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    days_of_week: list[int] = Field(..., min_length=1, max_length=7, description="0=Mon .. 6=Sun")
    reminder_time: time | None = None
    effective_from: date


class HabitBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    target: str | None = Field(default=None, max_length=100)


class HabitCreate(HabitBase):
    frequency: FrequencyEnum
    days_of_week: list[int] = Field(..., min_length=1, max_length=7)
    start_date: date | None = Field(default=None, description="Defaults to today (user-local); must be >= today")
    reminder_time: time | None = None


class HabitUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    target: str | None = Field(default=None, max_length=100)


class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: FrequencyEnum
    days_of_week: list[int] = Field(..., min_length=1, max_length=7)
    reminder_time: time | None = None
    effective_from: date | None = Field(default=None, description="Defaults to tomorrow (user-local); must be > today")


class Habit(HabitBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    frequency: FrequencyEnum
    start_date: date
    is_shared_habit: bool
    source_challenge_id: UUID | None
    archived_at: datetime | None
    created_at: datetime
    
    # Relationships
    schedules: list[ScheduleView] = Field(default_factory=list)
    
    schedule: ScheduleView | None = None
    pending_schedule: ScheduleView | None = None

# Habit Sheets

class SheetHabitView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    frequency: FrequencyEnum
    days_of_week: list[int]
    default_reminder_time: time | None
    target: str | None


class HabitSheetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    name: str
    category: str
    habits: list[SheetHabitView]


class HabitSheetList(BaseModel):
    sheets: list[HabitSheetView]


class HabitList(BaseModel):
    habits: list[Habit]


class HabitFromSheetOverrides(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reminder_time: time | None = None
    days_of_week: list[int] | None = Field(default=None, min_length=1, max_length=7)


class HabitFromSheet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sheet_habit_id: UUID
    start_date: date | None = None
    overrides: HabitFromSheetOverrides | None = None
