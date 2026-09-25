"""Occurrence tasks."""

import asyncio

from celery.schedules import crontab
from sqlalchemy import select, text

from app.db.session import async_session_factory
from app.models.user import User
from app.services.occurrence_service import rollover_and_generate_for_user
from app.worker import celery_app


async def _run_occurrence_rollover():
    async with async_session_factory() as db:
        # Find users where it is currently between midnight and 1 AM in their timezone
        stmt = select(User).where(
            text("EXTRACT(HOUR FROM (now() AT TIME ZONE timezone)) = 0")
        )
        result = await db.execute(stmt)
        users = result.scalars().all()
        
        for user in users:
            await rollover_and_generate_for_user(db, user)
        
        await db.commit()


@celery_app.task(name="tasks.occurrence_rollover_and_generate")
def occurrence_rollover_and_generate():
    """Celery task to roll over yesterday and generate today's occurrences."""
    asyncio.run(_run_occurrence_rollover())


@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Execute every hour at the top of the hour
    sender.add_periodic_task(
        crontab(minute=0),
        occurrence_rollover_and_generate.s(),
        name="hourly occurrence rollover and generation",
    )
