"""Create M1 planning core tables.

Revision ID: 0001_planning_core
Revises:
Create Date: 2026-08-24
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_planning_core"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_drafts",
        sa.Column("draft_id", sa.String(64), primary_key=True),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("travel_facts", sa.JSON(), nullable=True),
        sa.Column("selected_attraction_ids", sa.JSON(), nullable=False),
        sa.Column("visit_period_preferences", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_trip_drafts_principal_id", "trip_drafts", ["principal_id"])
    op.create_index("ix_trip_drafts_city_id", "trip_drafts", ["city_id"])

    op.create_table(
        "generation_intents",
        sa.Column("generation_intent_id", sa.String(64), primary_key=True),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("draft_id", sa.String(64), nullable=False),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("input_schema_version", sa.String(64), nullable=False),
        sa.Column("input_snapshot", sa.JSON(), nullable=False),
        sa.Column("input_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("data_snapshot_version", sa.String(128), nullable=False),
        sa.Column("random_seed", sa.Integer(), nullable=False),
        sa.Column("submitted_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.Column("trip_id", sa.String(64), nullable=True),
        sa.Column("trip_revision_id", sa.String(64), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index(
        "ix_generation_intents_principal_id", "generation_intents", ["principal_id"]
    )
    op.create_index("ix_generation_intents_draft_id", "generation_intents", ["draft_id"])
    op.create_index("ix_generation_intents_status", "generation_intents", ["status"])

    op.create_table(
        "trips",
        sa.Column("trip_id", sa.String(64), primary_key=True),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("source_draft_id", sa.String(64), nullable=False),
        sa.Column("current_revision_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_trips_principal_id", "trips", ["principal_id"])
    op.create_index("ix_trips_city_id", "trips", ["city_id"])
    op.create_index("ix_trips_source_draft_id", "trips", ["source_draft_id"])

    op.create_table(
        "trip_revisions",
        sa.Column("trip_revision_id", sa.String(64), primary_key=True),
        sa.Column("trip_id", sa.String(64), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("generation_intent_id", sa.String(64), nullable=False, unique=True),
        sa.Column("completion_kind", sa.String(32), nullable=False),
        sa.Column("has_soft_degradation", sa.Boolean(), nullable=False),
        sa.Column("result_schema_version", sa.String(64), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_snapshot_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )
    op.create_index("ix_trip_revisions_trip_id", "trip_revisions", ["trip_id"])

    op.create_table(
        "solver_runs",
        sa.Column("solver_run_id", sa.String(64), primary_key=True),
        sa.Column("generation_intent_id", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("quality_gate_passed", sa.Boolean(), nullable=False),
        sa.Column("solver_version", sa.String(64), nullable=False),
        sa.Column("constraint_version", sa.String(64), nullable=False),
        sa.Column("parameter_version", sa.String(64), nullable=False),
        sa.Column("audit_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_0900_ai_ci",
    )


def downgrade() -> None:
    op.drop_table("solver_runs")
    op.drop_index("ix_trip_revisions_trip_id", table_name="trip_revisions")
    op.drop_table("trip_revisions")
    op.drop_index("ix_trips_source_draft_id", table_name="trips")
    op.drop_index("ix_trips_city_id", table_name="trips")
    op.drop_index("ix_trips_principal_id", table_name="trips")
    op.drop_table("trips")
    op.drop_index("ix_generation_intents_status", table_name="generation_intents")
    op.drop_index("ix_generation_intents_draft_id", table_name="generation_intents")
    op.drop_index("ix_generation_intents_principal_id", table_name="generation_intents")
    op.drop_table("generation_intents")
    op.drop_index("ix_trip_drafts_city_id", table_name="trip_drafts")
    op.drop_index("ix_trip_drafts_principal_id", table_name="trip_drafts")
    op.drop_table("trip_drafts")
