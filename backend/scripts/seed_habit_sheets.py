"""Seed script for Habit Sheets."""

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.habit import FrequencyEnum
from app.models.sheet import HabitSheet, SheetHabit

SEED_DATA: list[dict[str, Any]] = [
    {
        "slug": "study",
        "name": "Study",
        "category": "Study",
        "sort_order": 1,
        "habits": [
            {
                "name": "DSA Practice",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 1,
            },
            {
                "name": "Read for 30 minutes",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 2,
            },
            {
                "name": "Revise today's topics",
                "frequency": FrequencyEnum.weekdays,
                "days_of_week": [0, 1, 2, 3, 4],
                "sort_order": 3,
            },
            {
                "name": "Solve 5 problems",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "target": "5 problems",
                "sort_order": 4,
            },
        ],
    },
    {
        "slug": "fitness",
        "name": "Fitness",
        "category": "Fitness",
        "sort_order": 2,
        "habits": [
            {
                "name": "Gym",
                "frequency": FrequencyEnum.custom,
                "days_of_week": [0, 2, 4],
                "sort_order": 1,
            },
            {
                "name": "10,000 steps",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "target": "10000 steps",
                "sort_order": 2,
            },
            {
                "name": "Drink sufficient water",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 3,
            },
            {
                "name": "Stretching",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 4,
            },
        ],
    },
    {
        # ASSUMPTION: The source documents do not specify exact habits for Productivity, Health, and Reading.
        # These are a minimal 2-3 habit placeholder set.
        "slug": "productivity",
        "name": "Productivity",
        "category": "Productivity",
        "sort_order": 3,
        "habits": [
            {
                "name": "Inbox Zero",
                "frequency": FrequencyEnum.weekdays,
                "days_of_week": [0, 1, 2, 3, 4],
                "sort_order": 1,
            },
            {
                "name": "Plan Tomorrow",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 2,
            },
        ],
    },
    {
        "slug": "health",
        "name": "Health",
        "category": "Health",
        "sort_order": 4,
        "habits": [
            {
                "name": "Take Vitamins",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "sort_order": 1,
            },
            {
                "name": "8 hours sleep",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "target": "8 hours",
                "sort_order": 2,
            },
        ],
    },
    {
        "slug": "reading",
        "name": "Reading",
        "category": "Reading",
        "sort_order": 5,
        "habits": [
            {
                "name": "Read 10 pages",
                "frequency": FrequencyEnum.daily,
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "target": "10 pages",
                "sort_order": 1,
            },
            {
                "name": "Listen to Audiobook",
                "frequency": FrequencyEnum.custom,
                "days_of_week": [5, 6],
                "sort_order": 2,
            },
        ],
    },
]


async def seed_sheets(db: AsyncSession) -> None:
    for sheet_data in SEED_DATA:
        slug = sheet_data["slug"]
        stmt = select(HabitSheet).where(HabitSheet.slug == slug)
        result = await db.execute(stmt)
        sheet = result.scalar_one_or_none()

        if not sheet:
            sheet = HabitSheet(
                slug=slug,
                name=sheet_data["name"],
                category=sheet_data["category"],
                sort_order=sheet_data["sort_order"],
            )
            db.add(sheet)
            await db.flush()

        for habit_data in sheet_data["habits"]:
            h_stmt = select(SheetHabit).where(
                SheetHabit.sheet_id == sheet.id,
                SheetHabit.name == habit_data["name"],
            )
            h_result = await db.execute(h_stmt)
            habit = h_result.scalar_one_or_none()

            if not habit:
                habit = SheetHabit(
                    sheet_id=sheet.id,
                    name=habit_data["name"],
                    frequency=habit_data["frequency"],
                    days_of_week=habit_data["days_of_week"],
                    target=habit_data.get("target"),
                    sort_order=habit_data["sort_order"],
                )
                db.add(habit)

    await db.commit()
    print("Habit sheets seeded successfully.")


async def main() -> None:
    async with async_session_factory() as session:
        await seed_sheets(session)


if __name__ == "__main__":
    asyncio.run(main())
