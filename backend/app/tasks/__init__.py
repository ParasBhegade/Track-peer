"""Celery tasks."""

from app.tasks.occurrences import occurrence_rollover_and_generate

__all__ = ["occurrence_rollover_and_generate"]
