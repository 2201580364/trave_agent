"""Add versioned place catalog and solver projection boundary.

Revision ID: 0006_place_catalog
Revises: 0005_feedbacks
Create Date: 2026-08-29
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_place_catalog"
down_revision = "0005_feedbacks"
branch_labels = None
depends_on = None

MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_0900_ai_ci",
}


def upgrade() -> None:
    op.create_table(
        "places",
        sa.Column("place_id", sa.String(64), primary_key=True),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("merged_into_place_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("updated_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["merged_into_place_id"], ["places.place_id"]),
        **MYSQL_OPTIONS,
    )
    op.create_index("ix_places_city_id", "places", ["city_id"])
    op.create_index("ix_places_status", "places", ["status"])

    op.create_table(
        "place_source_records",
        sa.Column("source_record_id", sa.String(64), primary_key=True),
        sa.Column("place_id", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("registry_id", sa.String(80), nullable=False),
        sa.Column("registry_sha256", sa.String(64), nullable=False),
        sa.Column("field_dictionary_id", sa.String(80), nullable=False),
        sa.Column("field_dictionary_sha256", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("collection_mode", sa.String(32), nullable=False),
        sa.Column("target_stage", sa.String(20), nullable=False),
        sa.Column("source_decision", sa.String(20), nullable=False),
        sa.Column("observed_at", sa.String(40), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.place_id"]),
        **MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_place_source_records_place_id", "place_source_records", ["place_id"]
    )
    op.create_index(
        "ix_place_source_records_source_id", "place_source_records", ["source_id"]
    )
    op.create_index(
        "ix_place_source_records_target_stage",
        "place_source_records",
        ["target_stage"],
    )
    op.create_index(
        "ix_place_source_records_status", "place_source_records", ["status"]
    )

    op.create_table(
        "place_revisions",
        sa.Column("place_revision_id", sa.String(64), primary_key=True),
        sa.Column("place_id", sa.String(64), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(24), nullable=False),
        sa.Column("canonical_name", sa.String(160), nullable=False),
        sa.Column("aliases", sa.JSON(), nullable=False),
        sa.Column("place_kind", sa.String(32), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("admin_area", sa.String(120), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("geometry_kind", sa.String(20), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("duration_recommended", sa.Integer(), nullable=False),
        sa.Column("duration_max", sa.Integer(), nullable=False),
        sa.Column("internal_travel_min", sa.Integer(), nullable=False),
        sa.Column("energy_level", sa.Integer(), nullable=False),
        sa.Column("indoor_outdoor", sa.String(20), nullable=False),
        sa.Column("suitable_periods", sa.JSON(), nullable=False),
        sa.Column("audience_tags", sa.JSON(), nullable=False),
        sa.Column("rain_suitability", sa.String(20), nullable=False),
        sa.Column("is_always_open", sa.Boolean(), nullable=False),
        sa.Column("solver_eligible", sa.Boolean(), nullable=False),
        sa.Column("conflicts_resolved", sa.Boolean(), nullable=False),
        sa.Column("source_record_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.Column("published_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["place_id"], ["places.place_id"]),
        sa.UniqueConstraint(
            "place_id", "revision_number", name="uq_place_revisions_place_number"
        ),
        **MYSQL_OPTIONS,
    )
    op.create_index("ix_place_revisions_place_id", "place_revisions", ["place_id"])
    op.create_index(
        "ix_place_revisions_lifecycle_status", "place_revisions", ["lifecycle_status"]
    )
    op.create_index(
        "ix_place_revisions_canonical_name", "place_revisions", ["canonical_name"]
    )
    op.create_index(
        "ix_place_revisions_place_kind", "place_revisions", ["place_kind"]
    )
    op.create_index(
        "ix_place_revisions_solver_eligible", "place_revisions", ["solver_eligible"]
    )

    op.create_table(
        "place_geometries",
        sa.Column("geometry_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("geometry_kind", sa.String(20), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        **MYSQL_OPTIONS,
    )
    _source_child_indexes("place_geometries")

    op.create_table(
        "place_access_points",
        sa.Column("access_point_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("access_point_kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("lat", sa.Numeric(10, 7), nullable=False),
        sa.Column("lng", sa.Numeric(10, 7), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("fetched_at", sa.String(40), nullable=True),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        **MYSQL_OPTIONS,
    )
    _source_child_indexes("place_access_points")
    op.create_index(
        "ix_place_access_points_access_point_kind",
        "place_access_points",
        ["access_point_kind"],
    )

    op.create_table(
        "place_time_rules",
        sa.Column("time_rule_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("rule_kind", sa.String(24), nullable=False),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=True),
        sa.Column("end_minute", sa.Integer(), nullable=True),
        sa.Column("last_entry_minute", sa.Integer(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        **MYSQL_OPTIONS,
    )
    _source_child_indexes("place_time_rules")
    op.create_index("ix_place_time_rules_rule_kind", "place_time_rules", ["rule_kind"])

    op.create_table(
        "place_closures",
        sa.Column("closure_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        sa.UniqueConstraint(
            "place_revision_id",
            "weekday",
            name="uq_place_closures_revision_weekday",
        ),
        **MYSQL_OPTIONS,
    )
    _source_child_indexes("place_closures")

    op.create_table(
        "place_date_exceptions",
        sa.Column("date_exception_id", sa.String(64), primary_key=True),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("exception_kind", sa.String(24), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=True),
        sa.Column("end_minute", sa.Integer(), nullable=True),
        sa.Column("last_entry_minute", sa.Integer(), nullable=True),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        sa.UniqueConstraint(
            "place_revision_id",
            "service_date",
            "exception_kind",
            name="uq_place_date_exceptions_revision_date_kind",
        ),
        **MYSQL_OPTIONS,
    )
    _source_child_indexes("place_date_exceptions")
    op.create_index(
        "ix_place_date_exceptions_service_date",
        "place_date_exceptions",
        ["service_date"],
    )

    op.create_table(
        "place_relations",
        sa.Column("relation_id", sa.String(64), primary_key=True),
        sa.Column("from_place_id", sa.String(64), nullable=False),
        sa.Column("to_place_id", sa.String(64), nullable=False),
        sa.Column("relation_type", sa.String(24), nullable=False),
        sa.Column("source_record_id", sa.String(64), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("resolution_status", sa.String(24), nullable=False),
        sa.Column("decision_note", sa.String(500), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["from_place_id"], ["places.place_id"]),
        sa.ForeignKeyConstraint(["to_place_id"], ["places.place_id"]),
        sa.ForeignKeyConstraint(
            ["source_record_id"], ["place_source_records.source_record_id"]
        ),
        sa.UniqueConstraint(
            "from_place_id",
            "to_place_id",
            "relation_type",
            name="uq_place_relations_direction_type",
        ),
        **MYSQL_OPTIONS,
    )
    for column in (
        "from_place_id",
        "to_place_id",
        "relation_type",
        "source_record_id",
        "review_status",
        "resolution_status",
        "active",
    ):
        op.create_index(f"ix_place_relations_{column}", "place_relations", [column])

    op.create_table(
        "selection_exclusion_groups",
        sa.Column("exclusion_group_id", sa.String(64), primary_key=True),
        sa.Column("city_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("review_status", sa.String(24), nullable=False),
        sa.Column("decision_note", sa.String(500), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("reviewed_at", sa.String(40), nullable=True),
        **MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_selection_exclusion_groups_city_id",
        "selection_exclusion_groups",
        ["city_id"],
    )
    op.create_index(
        "ix_selection_exclusion_groups_status",
        "selection_exclusion_groups",
        ["status"],
    )
    op.create_index(
        "ix_selection_exclusion_groups_review_status",
        "selection_exclusion_groups",
        ["review_status"],
    )

    op.create_table(
        "selection_exclusion_members",
        sa.Column("exclusion_group_id", sa.String(64), primary_key=True),
        sa.Column("place_id", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.ForeignKeyConstraint(
            ["exclusion_group_id"],
            ["selection_exclusion_groups.exclusion_group_id"],
        ),
        sa.ForeignKeyConstraint(["place_id"], ["places.place_id"]),
        sa.UniqueConstraint(
            "exclusion_group_id",
            "place_id",
            name="uq_selection_exclusion_members_group_place",
        ),
        **MYSQL_OPTIONS,
    )
    op.create_index(
        "ix_selection_exclusion_members_place_id",
        "selection_exclusion_members",
        ["place_id"],
    )

    op.create_table(
        "solver_place_projections",
        sa.Column("projection_id", sa.String(64), primary_key=True),
        sa.Column("projection_version", sa.String(64), nullable=False),
        sa.Column("data_snapshot_version", sa.String(128), nullable=False),
        sa.Column("place_id", sa.String(64), nullable=False),
        sa.Column("place_revision_id", sa.String(64), nullable=False),
        sa.Column("solver_node_id", sa.Integer(), nullable=False),
        sa.Column("place_kind", sa.String(32), nullable=False),
        sa.Column("geometry_kind", sa.String(20), nullable=False),
        sa.Column("arrival_access_point_id", sa.String(64), nullable=False),
        sa.Column("departure_access_point_id", sa.String(64), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("duration_recommended", sa.Integer(), nullable=False),
        sa.Column("duration_max", sa.Integer(), nullable=False),
        sa.Column("internal_travel_min", sa.Integer(), nullable=False),
        sa.Column("solver_payload", sa.JSON(), nullable=False),
        sa.Column("projection_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("gate_reason_codes", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(40), nullable=False),
        sa.Column("published_at", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["place_id"], ["places.place_id"]),
        sa.ForeignKeyConstraint(
            ["place_revision_id"], ["place_revisions.place_revision_id"]
        ),
        sa.ForeignKeyConstraint(
            ["arrival_access_point_id"], ["place_access_points.access_point_id"]
        ),
        sa.ForeignKeyConstraint(
            ["departure_access_point_id"], ["place_access_points.access_point_id"]
        ),
        sa.UniqueConstraint(
            "data_snapshot_version",
            "solver_node_id",
            name="uq_solver_place_projections_snapshot_node",
        ),
        sa.UniqueConstraint(
            "data_snapshot_version",
            "place_revision_id",
            name="uq_solver_place_projections_snapshot_revision",
        ),
        **MYSQL_OPTIONS,
    )
    for column in (
        "projection_version",
        "data_snapshot_version",
        "place_id",
        "place_revision_id",
        "projection_hash",
        "status",
    ):
        op.create_index(
            f"ix_solver_place_projections_{column}",
            "solver_place_projections",
            [column],
        )


def downgrade() -> None:
    op.drop_table("solver_place_projections")
    op.drop_table("selection_exclusion_members")
    op.drop_table("selection_exclusion_groups")
    op.drop_table("place_relations")
    op.drop_table("place_date_exceptions")
    op.drop_table("place_closures")
    op.drop_table("place_time_rules")
    op.drop_table("place_access_points")
    op.drop_table("place_geometries")
    op.drop_table("place_revisions")
    op.drop_table("place_source_records")
    op.drop_table("places")


def _source_child_indexes(table: str) -> None:
    for column in ("place_revision_id", "source_record_id", "review_status", "active"):
        op.create_index(f"ix_{table}_{column}", table, [column])
