"""Track the holiday calendar used to materialize a date exception.

Revision ID: 0015_holiday_exception_provenance
Revises: 0014_holiday_calendar_sync
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_holiday_exception_provenance"
down_revision = "0014_holiday_calendar_sync"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("place_date_exceptions") as batch:
        batch.add_column(sa.Column("holiday_calendar_id", sa.String(64), nullable=True))
        batch.create_foreign_key(
            "fk_place_date_exceptions_holiday_calendar",
            "holiday_calendars",
            ["holiday_calendar_id"],
            ["holiday_calendar_id"],
        )
        batch.create_index(
            "ix_place_date_exceptions_holiday_calendar_id",
            ["holiday_calendar_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("place_date_exceptions") as batch:
        batch.drop_index("ix_place_date_exceptions_holiday_calendar_id")
        batch.drop_constraint(
            "fk_place_date_exceptions_holiday_calendar", type_="foreignkey"
        )
        batch.drop_column("holiday_calendar_id")
