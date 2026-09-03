"""Persist versioned China holiday calendars and synchronization jobs.

Revision ID: 0014_holiday_calendar_sync
Revises: 0013_backfill_solver_eligibility
"""

import sqlalchemy as sa
from alembic import op

revision = "0014_holiday_calendar_sync"
down_revision = "0013_backfill_solver_eligibility"
branch_labels = None
depends_on = None

MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "holiday_calendars",
        sa.Column("holiday_calendar_id", sa.String(64), primary_key=True),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("source_content_sha256", sa.String(64), nullable=False),
        sa.Column("normalized_digest", sa.String(64), nullable=False),
        sa.Column("supersedes_calendar_id", sa.String(64), nullable=True),
        sa.Column("published_at", sa.String(40), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["supersedes_calendar_id"], ["holiday_calendars.holiday_calendar_id"]
        ),
        sa.UniqueConstraint(
            "region_code", "calendar_year", "version", name="uq_holiday_calendar_version"
        ),
        sa.UniqueConstraint(
            "region_code",
            "calendar_year",
            "normalized_digest",
            name="uq_holiday_calendar_content",
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_holiday_calendars_region_year_status",
        "holiday_calendars",
        ["region_code", "calendar_year", "status"],
    )
    op.create_table(
        "holiday_periods",
        sa.Column("holiday_period_id", sa.String(64), primary_key=True),
        sa.Column(
            "holiday_calendar_id",
            sa.String(64),
            sa.ForeignKey("holiday_calendars.holiday_calendar_id"),
            nullable=False,
        ),
        sa.Column("holiday_name", sa.String(80), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("evidence_quote", sa.String(1000), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "holiday_calendar_id", "display_order", name="uq_holiday_period_order"
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_holiday_periods_calendar", "holiday_periods", ["holiday_calendar_id"]
    )
    op.create_table(
        "holiday_adjusted_workdays",
        sa.Column("adjusted_workday_id", sa.String(64), primary_key=True),
        sa.Column(
            "holiday_calendar_id",
            sa.String(64),
            sa.ForeignKey("holiday_calendars.holiday_calendar_id"),
            nullable=False,
        ),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("holiday_name", sa.String(80), nullable=False),
        sa.Column("evidence_quote", sa.String(1000), nullable=False),
        sa.UniqueConstraint(
            "holiday_calendar_id", "service_date", name="uq_holiday_adjusted_workday_date"
        ),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_holiday_adjusted_workdays_calendar",
        "holiday_adjusted_workdays",
        ["holiday_calendar_id"],
    )
    op.create_table(
        "holiday_calendar_sync_jobs",
        sa.Column("sync_job_id", sa.String(64), primary_key=True),
        sa.Column("region_code", sa.String(16), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("source_title", sa.String(300), nullable=True),
        sa.Column("source_published_at", sa.String(40), nullable=True),
        sa.Column("source_content_sha256", sa.String(64), nullable=True),
        sa.Column("validation_result", sa.JSON(), nullable=False),
        sa.Column("calendar_id", sa.String(64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.String(40), nullable=True),
        sa.Column("operation_intent_id", sa.String(64), nullable=False, unique=True),
        sa.Column("operation_digest", sa.String(64), nullable=False),
        sa.Column("run_lock_key", sa.String(40), nullable=True, unique=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("started_at", sa.String(40), nullable=True),
        sa.Column("finished_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["calendar_id"], ["holiday_calendars.holiday_calendar_id"]),
        **MYSQL_TABLE_ARGS,
    )
    op.create_index(
        "ix_holiday_sync_jobs_region_year_status",
        "holiday_calendar_sync_jobs",
        ["region_code", "calendar_year", "status"],
    )


def downgrade() -> None:
    op.drop_table("holiday_calendar_sync_jobs")
    op.drop_table("holiday_adjusted_workdays")
    op.drop_table("holiday_periods")
    op.drop_table("holiday_calendars")
