"""Persist candidate revision data-quality and review flags.

Revision ID: 0009_place_revision_review_flags
Revises: 0008_place_review_workflow
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_place_revision_review_flags"
down_revision = "0008_place_review_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "place_revisions",
        sa.Column("review_flags", sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE place_revisions SET review_flags = :empty "
            "WHERE review_flags IS NULL"
        ).bindparams(empty="[]")
    )
    # SQLite cannot alter a column's nullability in place. The application
    # normalizes NULL to an empty tuple, so keeping this JSON column nullable
    # preserves compatibility with both SQLite and MySQL.


def downgrade() -> None:
    op.drop_column("place_revisions", "review_flags")
