"""Add immutable, redacted M1 plan-share snapshots.

Revision ID: 0004_plan_shares
Revises: 0003_trip_revision_lineage
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0004_plan_shares"
down_revision = "0003_trip_revision_lineage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plan_shares",
        sa.Column("plan_share_id", sa.String(64), primary_key=True),
        sa.Column("plan_share_intent_id", sa.String(64), nullable=False),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("trip_id", sa.String(64), nullable=False),
        sa.Column("revision_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("template", sa.String(20), nullable=False),
        sa.Column("public_token_hash", sa.String(64), nullable=False),
        sa.Column("share_schema_version", sa.String(32), nullable=False),
        sa.Column("share_snapshot", sa.JSON(), nullable=False),
        sa.Column("share_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("published_at", sa.String(40), nullable=False),
        sa.Column("revoked_at", sa.String(40), nullable=True),
        sa.UniqueConstraint(
            "plan_share_intent_id",
            name="uq_plan_shares_intent",
        ),
        sa.UniqueConstraint(
            "public_token_hash",
            name="uq_plan_shares_public_token_hash",
        ),
    )
    op.create_index(
        "ix_plan_shares_principal_id",
        "plan_shares",
        ["principal_id"],
    )
    op.create_index("ix_plan_shares_trip_id", "plan_shares", ["trip_id"])
    op.create_index(
        "ix_plan_shares_revision_id",
        "plan_shares",
        ["revision_id"],
    )
    op.create_index("ix_plan_shares_status", "plan_shares", ["status"])


def downgrade() -> None:
    op.drop_index("ix_plan_shares_status", table_name="plan_shares")
    op.drop_index("ix_plan_shares_revision_id", table_name="plan_shares")
    op.drop_index("ix_plan_shares_trip_id", table_name="plan_shares")
    op.drop_index("ix_plan_shares_principal_id", table_name="plan_shares")
    op.drop_table("plan_shares")
