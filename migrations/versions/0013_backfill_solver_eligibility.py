"""Backfill solver eligibility for revisions already approved by reviewers.

Revision ID: 0013_backfill_solver_eligibility
Revises: 0012_relation_review_status
"""

from alembic import op
import sqlalchemy as sa

revision = "0013_backfill_solver_eligibility"
down_revision = "0012_relation_review_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE place_revisions "
            "SET solver_eligible = :eligible "
            "WHERE lifecycle_status IN ('human_verified', 'published')"
        ).bindparams(eligible=True)
    )


def downgrade() -> None:
    # Eligibility is derived from the reviewed state; do not invalidate
    # previously approved revisions on downgrade.
    pass
