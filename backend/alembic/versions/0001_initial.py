"""0001_initial — Foundation schema

Creates: users, habits, schedules, refresh_tokens, password_reset_tokens,
         habit_sheets, sheet_habits.

Schema follows Phase 2 §2 + Phase 3 §5 exactly.

Revision ID: 0001
Revises: None
Create Date: 2026-09-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Shared enum
habit_frequency = postgresql.ENUM("daily", "weekdays", "custom", name="habit_frequency", create_type=False)


def upgrade() -> None:
    # ── Enum type ────────────────────────────────────────
    habit_frequency_type = sa.Enum("daily", "weekdays", "custom", name="habit_frequency")
    habit_frequency_type.create(op.get_bind(), checkfirst=True)

    # ── users ────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=True, comment="null if OAuth-only account"),
        sa.Column("google_oauth_id", sa.String(256), nullable=True, unique=True),
        sa.Column("timezone", sa.String(64), nullable=False, comment="IANA tz name, e.g. Asia/Kolkata"),
        sa.Column("display_name", sa.String(50), nullable=False),
        sa.Column("goal", sa.Text, nullable=True, comment="doubles as profile bio"),
        sa.Column("avatar_url", sa.Text, nullable=True, comment="URL only in MVP; upload flow deferred (FR-2.1)"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    # ── habits ───────────────────────────────────────────
    op.create_table(
        "habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("target", sa.Text, nullable=True, comment='optional target, e.g. "1 problem/day" (FR-3.1)'),
        sa.Column("frequency", habit_frequency, nullable=False, comment="derived label — schedules.days_of_week is the source of truth"),
        sa.Column("start_date", sa.Date, nullable=False, comment="must be >= today in user timezone at creation"),
        sa.Column("is_shared_habit", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("source_challenge_id", postgresql.UUID(as_uuid=True), nullable=True, comment="set only if is_shared_habit; FK added in challenges migration"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True, comment="soft delete"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_habits_user_id_active",
        "habits",
        ["user_id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )

    # ── schedules ────────────────────────────────────────
    op.create_table(
        "schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("habit_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer), nullable=False, comment="0=Mon..6=Sun"),
        sa.Column("reminder_time", sa.Time, nullable=True),
        sa.Column("effective_from", sa.Date, nullable=False, comment="user-local date; edits create a new row (must be >= tomorrow)"),
    )
    op.create_unique_constraint("uq_schedules_habit_effective", "schedules", ["habit_id", "effective_from"])
    op.create_check_constraint("ck_schedules_days_count", "schedules", sa.text("cardinality(days_of_week) BETWEEN 1 AND 7"))
    op.create_index("ix_schedules_habit_effective_desc", "schedules", ["habit_id", sa.text("effective_from DESC")])

    # ── refresh_tokens ───────────────────────────────────
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text, unique=True, nullable=False, comment="SHA-256 of the opaque token; raw token never stored"),
        sa.Column("family_id", postgresql.UUID(as_uuid=True), nullable=False, comment="all rotations from one login share a family"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="7 days from creation"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])

    # ── password_reset_tokens ────────────────────────────
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text, unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, comment="30 minutes"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True, comment="single-use"),
    )

    # ── habit_sheets ─────────────────────────────────────
    op.create_table(
        "habit_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.Text, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False, comment="Fitness, Study, Productivity, Health, Reading (FR-3.2)"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
    )

    # ── sheet_habits ─────────────────────────────────────
    op.create_table(
        "sheet_habits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sheet_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("habit_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("frequency", habit_frequency, nullable=False),
        sa.Column("days_of_week", postgresql.ARRAY(sa.Integer), nullable=False),
        sa.Column("default_reminder_time", sa.Time, nullable=True),
        sa.Column("target", sa.Text, nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_table("sheet_habits")
    op.drop_table("habit_sheets")
    op.drop_table("password_reset_tokens")
    op.drop_table("refresh_tokens")
    op.drop_table("schedules")
    op.drop_table("habits")
    op.drop_table("users")

    # Drop the enum type
    sa.Enum(name="habit_frequency").drop(op.get_bind(), checkfirst=True)
