from datetime import datetime
from uuid import UUID
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

# Computed once at import time
VALID_TIMEZONES = available_timezones()


class UserBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)
    avatar_url: str | None = None
    timezone: str
    goal: str | None = Field(default=None, max_length=200)


class User(UserBase):
    id: UUID
    email: EmailStr
    has_password: bool
    google_linked: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: HttpUrl | None = None
    timezone: str | None = None
    goal: str | None = Field(default=None, max_length=200)

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_TIMEZONES:
            raise ValueError(f"Invalid timezone: {v}")
        return v
