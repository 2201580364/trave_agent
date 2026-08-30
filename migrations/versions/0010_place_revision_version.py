"""Add an optimistic-lock version to place revisions.

Revision ID: 0010_place_revision_version
Revises: 0009_place_revision_review_flags
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_place_revision_version"
down_revision = "0009_place_revision_review_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "place_revisions",
        sa.Column("revision_version", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE place_revisions SET revision_version = :initial "
            "WHERE revision_version IS NULL"
        ).bindparams(initial=1)
    )


def downgrade() -> None:
    op.drop_column("place_revisions", "revision_version")
