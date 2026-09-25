from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class UserBase(BaseModel):
    display_name: str = Field(min_length=1, max_length=50)
    avatar_url: HttpUrl | str | None = None
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
    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: HttpUrl | str | None = None
    timezone: str | None = None
    goal: str | None = Field(default=None, max_length=200)
