from datetime import date, time
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReminderItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notification_id: str
    habit_id: UUID
    habit_name: str
    occurrence_date: date
    reminder_time: time


class ReminderPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    timezone: str
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    reminders: list[ReminderItem]
