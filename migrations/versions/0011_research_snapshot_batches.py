"""Add immutable research snapshot and publication batch metadata."""

import sqlalchemy as sa
from alembic import op

revision = "0011_research_snapshot_batches"
down_revision = "0010_place_revision_version"
branch_labels = None
depends_on = None

MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}

def upgrade() -> None:
    op.create_table("publication_batches",
        sa.Column("batch_id", sa.String(64), primary_key=True),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("operation_intent_id", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("snapshot_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("operation_intent_id", name="uq_publication_batches_intent"),
        **MYSQL_OPTIONS,
    )
    op.create_table("publication_batch_items",
        sa.Column("batch_item_id", sa.String(64), primary_key=True),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("reason_codes", sa.JSON(), nullable=False),
        sa.Column("projection_id", sa.String(64), nullable=True),
        sa.Column("published_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["publication_batches.batch_id"]),
        sa.ForeignKeyConstraint(["place_revision_id"], ["place_revisions.place_revision_id"]),
        sa.UniqueConstraint("batch_id", "place_revision_id", name="uq_publication_batch_revision"),
        **MYSQL_OPTIONS,
    )
    op.create_table("research_snapshots",
        sa.Column("snapshot_id", sa.String(64), primary_key=True),
        sa.Column("data_snapshot_version", sa.String(80), nullable=False),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("source_batch_id", sa.String(64), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(["source_batch_id"], ["publication_batches.batch_id"]),
        sa.UniqueConstraint("data_snapshot_version", name="uq_research_snapshots_version"),
        sa.UniqueConstraint("content_sha256", name="uq_research_snapshots_hash"), **MYSQL_OPTIONS)

def downgrade() -> None:
    op.drop_table("research_snapshots")
    op.drop_table("publication_batch_items")
    op.drop_table("publication_batches")
