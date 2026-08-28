"""Add structured revision and node feedback.

Revision ID: 0005_feedbacks
Revises: 0004_plan_shares
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_feedbacks"
down_revision = "0004_plan_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedbacks",
        sa.Column("feedback_id", sa.String(64), primary_key=True),
        sa.Column("feedback_intent_id", sa.String(64), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("trip_id", sa.String(64), nullable=False),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("feedback_scope", sa.String(20), nullable=False),
        sa.Column("target_key", sa.String(96), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=True),
        sa.Column("rating", sa.String(20), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint(
            "feedback_intent_id",
            name="uq_feedbacks_intent",
        ),
        sa.UniqueConstraint(
            "principal_id",
            "revision_id",
            "target_key",
            name="uq_feedbacks_principal_revision_target",
        ),
    )
    op.create_index("ix_feedbacks_principal_id", "feedbacks", ["principal_id"])
    op.create_index("ix_feedbacks_trip_id", "feedbacks", ["trip_id"])
    op.create_index("ix_feedbacks_revision_id", "feedbacks", ["revision_id"])
    op.create_index(
        "ix_feedbacks_feedback_scope",
        "feedbacks",
        ["feedback_scope"],
    )
    op.create_index("ix_feedbacks_rating", "feedbacks", ["rating"])


def downgrade() -> None:
    op.drop_index("ix_feedbacks_rating", table_name="feedbacks")
    op.drop_index("ix_feedbacks_feedback_scope", table_name="feedbacks")
    op.drop_index("ix_feedbacks_revision_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_trip_id", table_name="feedbacks")
    op.drop_index("ix_feedbacks_principal_id", table_name="feedbacks")
    op.drop_table("feedbacks")
