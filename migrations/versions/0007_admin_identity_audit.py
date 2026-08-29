"""Add independent administrator identity, RBAC, sessions, and audit.

Revision ID: 0007_admin_identity_audit
Revises: 0006_place_catalog
Create Date: 2026-08-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_admin_identity_audit"
down_revision = "0006_place_catalog"
branch_labels = None
depends_on = None

MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "admin_actors",
        sa.Column("admin_actor_id", sa.String(64), primary_key=True),
        sa.Column("login_name", sa.String(64), nullable=False),
        sa.Column("credential_digest", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.UniqueConstraint("login_name", name="uq_admin_actors_login_name"),
        **MYSQL_OPTIONS,
    )
    op.create_index("ix_admin_actors_login_name", "admin_actors", ["login_name"])
    op.create_index("ix_admin_actors_status", "admin_actors", ["status"])

    role_table = op.create_table(
        "admin_roles",
        sa.Column("role_key", sa.String(40), primary_key=True),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("enabled_milestone", sa.String(16), nullable=False),
        **MYSQL_OPTIONS,
    )
    op.bulk_insert(
        role_table,
        [
            {
                "role_key": "data_editor",
                "description": "编辑候选地点和 Revision",
                "enabled_milestone": "OM1",
            },
            {
                "role_key": "data_reviewer",
                "description": "审核地点事实和关系裁决",
                "enabled_milestone": "OM1",
            },
            {
                "role_key": "data_publisher",
                "description": "运行发布门并发布研究快照",
                "enabled_milestone": "OM1",
            },
            {
                "role_key": "research_viewer",
                "description": "只读查看研究数据和快照",
                "enabled_milestone": "OM1",
            },
            {
                "role_key": "content_moderator",
                "description": "处理评论和社区内容",
                "enabled_milestone": "OM3",
            },
            {
                "role_key": "admin_security",
                "description": "管理管理员身份、角色和安全审计",
                "enabled_milestone": "OM1",
            },
        ],
    )

    op.create_table(
        "admin_actor_roles",
        sa.Column("admin_actor_id", sa.String(64), primary_key=True),
        sa.Column("role_key", sa.String(40), primary_key=True),
        sa.Column("granted_by", sa.String(64), nullable=False),
        sa.Column("granted_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["admin_actor_id"], ["admin_actors.admin_actor_id"]),
        sa.ForeignKeyConstraint(["role_key"], ["admin_roles.role_key"]),
        sa.UniqueConstraint(
            "admin_actor_id",
            "role_key",
            name="uq_admin_actor_roles_actor_role",
        ),
        **MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_admin_actor_roles_role_key", "admin_actor_roles", ["role_key"]
    )

    op.create_table(
        "admin_sessions",
        sa.Column("admin_session_id", sa.String(64), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("admin_actor_id", sa.String(64), nullable=False),
        sa.Column("issued_role_keys", sa.JSON(), nullable=False),
        sa.Column("session_version", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.String(40), nullable=False),
        sa.Column("revoked_at", sa.String(40), nullable=True),
        sa.Column("client_ip_hash", sa.String(64), nullable=True),
        sa.Column("user_agent_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["admin_actor_id"], ["admin_actors.admin_actor_id"]),
        sa.UniqueConstraint("token_hash", name="uq_admin_sessions_token_hash"),
        **MYSQL_OPTIONS,
    )
    for column in ("token_hash", "admin_actor_id", "expires_at", "revoked_at"):
        op.create_index(f"ix_admin_sessions_{column}", "admin_sessions", [column])

    op.create_table(
        "admin_audit_events",
        sa.Column("audit_event_id", sa.String(64), primary_key=True),
        sa.Column("actor_id", sa.String(64), nullable=False),
        sa.Column("actor_role", sa.String(40), nullable=False),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("target_revision", sa.String(64), nullable=True),
        sa.Column("before_digest", sa.String(64), nullable=True),
        sa.Column("after_digest", sa.String(64), nullable=True),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.Column("reason_text", sa.String(500), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=False),
        sa.Column("operation_intent_id", sa.String(64), nullable=True),
        sa.Column("operation_digest", sa.String(64), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("occurred_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["admin_actors.admin_actor_id"]),
        sa.UniqueConstraint(
            "operation_intent_id",
            name="uq_admin_audit_events_operation_intent_id",
        ),
        **MYSQL_OPTIONS,
    )
    for column in (
        "actor_id",
        "actor_role",
        "action",
        "target_type",
        "target_id",
        "reason_code",
        "request_id",
        "result",
        "occurred_at",
    ):
        op.create_index(
            f"ix_admin_audit_events_{column}", "admin_audit_events", [column]
        )
    op.create_index(
        "ix_admin_audit_events_operation_intent_id",
        "admin_audit_events",
        ["operation_intent_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("admin_audit_events")
    op.drop_table("admin_sessions")
    op.drop_table("admin_actor_roles")
    op.drop_table("admin_roles")
    op.drop_table("admin_actors")
