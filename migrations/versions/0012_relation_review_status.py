"""Record completion of revision-scoped O07 relationship review.

Revision ID: 0012_relation_review_status
Revises: 0011_research_snapshot_batches
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_relation_review_status"
down_revision = "0011_research_snapshot_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("place_revisions")}
    if "relation_review_status" not in columns:
        op.add_column(
            "place_revisions",
            sa.Column("relation_review_status", sa.String(24), nullable=False, server_default="not_required"),
        )


def downgrade() -> None:
    op.drop_column("place_revisions", "relation_review_status")
