"""Add lineage for user-created trip revisions.

Revision ID: 0003_trip_revision_lineage
Revises: 0002_anonymous_identity
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_trip_revision_lineage"
down_revision = "0002_anonymous_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("generation_intents") as batch:
        batch.add_column(sa.Column("target_trip_id", sa.String(64), nullable=True))
        batch.add_column(sa.Column("base_revision_id", sa.String(64), nullable=True))
        batch.create_index(
            "ix_generation_intents_target_trip_id",
            ["target_trip_id"],
            unique=False,
        )
    with op.batch_alter_table("trip_revisions") as batch:
        batch.create_unique_constraint(
            "uq_trip_revisions_trip_number",
            ["trip_id", "revision_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("trip_revisions") as batch:
        batch.drop_constraint(
            "uq_trip_revisions_trip_number",
            type_="unique",
        )
    with op.batch_alter_table("generation_intents") as batch:
        batch.drop_index("ix_generation_intents_target_trip_id")
        batch.drop_column("base_revision_id")
        batch.drop_column("target_trip_id")
