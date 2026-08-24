"""Create anonymous identity credentials.

Revision ID: 0002_anonymous_identity
Revises: 0001_planning_core
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_anonymous_identity"
down_revision = "0001_planning_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anonymous_credentials",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("principal_id", sa.String(64), nullable=False, unique=True),
        sa.Column("device_installation_id", sa.String(128), nullable=True),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index(
        "ix_anonymous_credentials_principal_id",
        "anonymous_credentials",
        ["principal_id"],
        unique=True,
    )
    op.create_index(
        "ix_anonymous_credentials_expires_at",
        "anonymous_credentials",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_anonymous_credentials_expires_at",
        table_name="anonymous_credentials",
    )
    op.drop_index(
        "ix_anonymous_credentials_principal_id",
        table_name="anonymous_credentials",
    )
    op.drop_table("anonymous_credentials")
