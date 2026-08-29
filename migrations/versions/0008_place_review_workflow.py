"""Add append-only place review tasks and decisions.

Revision ID: 0008_place_review_workflow
Revises: 0007_admin_identity_audit
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_place_review_workflow"
down_revision = "0007_admin_identity_audit"
branch_labels = None
depends_on = None

MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "place_review_tasks",
        sa.Column("review_task_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("assigned_reviewer_id", sa.String(64), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["place_revision_id"], ["place_revisions.place_revision_id"]),
        sa.ForeignKeyConstraint(["assigned_reviewer_id"], ["admin_actors.admin_actor_id"]),
        sa.ForeignKeyConstraint(["created_by"], ["admin_actors.admin_actor_id"]),
        sa.UniqueConstraint(
            "place_revision_id", "status", name="uq_place_review_tasks_revision_status"
        ),
        **MYSQL_OPTIONS,
    )
    for column in ("place_revision_id", "status", "assigned_reviewer_id", "created_by"):
        op.create_index(f"ix_place_review_tasks_{column}", "place_review_tasks", [column])

    op.create_table(
        "place_review_decisions",
        sa.Column("review_decision_id", sa.String(64), primary_key=True),
        sa.Column("review_task_id", sa.String(64), nullable=False),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("actor_role", sa.String(40), nullable=False),
        sa.Column("decision_kind", sa.String(32), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("reason_text", sa.String(500), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["review_task_id"], ["place_review_tasks.review_task_id"]),
        sa.ForeignKeyConstraint(["place_revision_id"], ["place_revisions.place_revision_id"]),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_actors.admin_actor_id"]),
        **MYSQL_OPTIONS,
    )
    for column in (
        "review_task_id",
        "place_revision_id",
        "actor_id",
        "actor_role",
        "decision_kind",
        "reason_code",
        "created_at",
    ):
        op.create_index(f"ix_place_review_decisions_{column}", "place_review_decisions", [column])


def downgrade() -> None:
    op.drop_table("place_review_decisions")
    op.drop_table("place_review_tasks")
