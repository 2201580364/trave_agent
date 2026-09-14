"""Allow descriptive migration identifiers longer than Alembic's default."""

import sqlalchemy as sa
from alembic import op

revision = "0016_expand_alembic_version"
down_revision = "0015_holiday_exception_provenance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("alembic_version") as batch:
        batch.alter_column(
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    # Existing revision identifiers may exceed 32 characters; shrinking would
    # make downgrade unsafe and is intentionally unsupported.
    pass
