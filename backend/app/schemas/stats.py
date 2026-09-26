from datetime import date

from pydantic import BaseModel


class CalendarDaySummary(BaseModel):
    date: date
    scheduled: int
    completed: int
    percent: int | None

class CalendarSummaryResponse(BaseModel):
    days: list[CalendarDaySummary]

class HabitStatsResponse(BaseModel):
    current_streak: int
    longest_streak: int
    total_completions: int
    weekly_completion_percent: int | None
    monthly_completion_percent: int | None

class AccountStatsResponse(BaseModel):
    total_active_habits: int
    weekly_completion_percent: int | None
    best_current_streak: int
    total_lifetime_completions: int
