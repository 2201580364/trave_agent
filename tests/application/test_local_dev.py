"""A6-7 local browser-validation composition tests. Traceability: H3."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from travel_agent.local_dev import build_local_dev_app, build_local_hangzhou_catalog
from travel_agent.infrastructure.database import DatabaseSettings, build_engine, build_session_factory
from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceRevisionRow,
    PlaceRow,
    ResearchSnapshotRow,
    SolverPlaceProjectionRow,
)


def test_local_catalog_is_explicit_and_covers_evening_attraction() -> None:
    snapshots, catalog = build_local_hangzhou_catalog(
        reference_date=date(2026, 8, 25)
    )

    published = catalog.load(snapshots.current_version("hangzhou"))
    by_id = {item.external_id: item.attraction for item in published.attractions}

    assert len(published.attractions) == 7
    assert published.od_basis == "approximate_local_fixture"
    assert by_id["attr_fountain_show"].time_rules[0].open_min == 18 * 60 + 30
    assert by_id["attr_fountain_show"].time_rules[0].close_min == 19 * 60
    assert all(item.attraction.data_verified for item in published.attractions)


def test_local_app_uses_migrated_database_and_serves_catalog(
    tmp_path: Path, monkeypatch
) -> None:
    database_path = tmp_path / "local-dev.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migration = Config("alembic.ini")
    migration.attributes["skip_dotenv"] = True
    migration.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(migration, "head")
    monkeypatch.setenv("TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN", "local.admin")
    monkeypatch.setenv(
        "TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD", "Local-Admin-Password-2026!"
    )

    client = TestClient(
        build_local_dev_app(
            database_url=database_url,
            reference_date=date(2026, 8, 25),
        )
    )

    assert client.get("/health/ready").json()["ready"] is True
    session = client.post(
        "/api/v1/anonymous-sessions",
        json={"device_installation_id": "local-dev-test-device"},
    )
    token = session.json()["access_token"]
    response = client.get(
        "/api/v1/attractions",
        params={"city_id": "hangzhou"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert len(response.json()["items"]) == 7
    admin_session = client.post(
        "/api/v1/admin/sessions",
        json={
            "login_name": "local.admin",
            "password": "Local-Admin-Password-2026!",
        },
    )
    assert admin_session.status_code == 201
    assert "admin_security" in admin_session.json()["role_keys"]


def test_local_app_prefers_database_published_projection(tmp_path: Path) -> None:
    database_path = tmp_path / "published.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    migration = Config("alembic.ini")
    migration.attributes["skip_dotenv"] = True
    migration.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(migration, "head")
    engine = build_engine(DatabaseSettings(url=database_url))
    sessions = build_session_factory(engine)
    with sessions() as session:
        session.add(PlaceRow(
            place_id="published-place",
            city_id="hangzhou",
            status="active",
            merged_into_place_id=None,
            created_at="2026-08-01T00:00:00+00:00",
            updated_at="2026-08-01T00:00:00+00:00",
        ))
        session.add(PlaceRevisionRow(
            place_revision_id="published-revision",
            place_id="published-place",
            revision_number=1,
            revision_version=1,
            lifecycle_status="published",
            canonical_name="数据库发布景点",
            aliases=[], place_kind="attraction", category="景点", admin_area="杭州",
            address="杭州", geometry_kind="point", duration_min=30,
            duration_recommended=90, duration_max=120, internal_travel_min=5,
            energy_level=2, indoor_outdoor="outdoor", suitable_periods=[],
            audience_tags=[], rain_suitability="conditional", is_always_open=True,
            solver_eligible=True, conflicts_resolved=True, source_record_ids=[],
            created_at="2026-08-01T00:00:00+00:00", reviewed_at="2026-08-01T00:00:00+00:00",
            published_at="2026-08-30T00:00:00+00:00", review_flags=[], relation_review_status="no_relations",
        ))
        session.add(PlaceAccessPointRow(
            access_point_id="published-access", place_revision_id="published-revision",
            access_point_kind="visitor_entrance", name="入口", lat=30.25, lng=120.16,
            source_record_id="missing-source", review_status="human_verified", active=True,
            fetched_at="2026-08-01T00:00:00+00:00", reviewed_at="2026-08-01T00:00:00+00:00",
            created_at="2026-08-01T00:00:00+00:00",
        ))
        session.add(SolverPlaceProjectionRow(
            projection_id="published-projection", projection_version="projection-v1",
            data_snapshot_version="db-published-v1", place_id="published-place",
            place_revision_id="published-revision", solver_node_id=101,
            place_kind="attraction", geometry_kind="point",
            arrival_access_point_id="published-access", departure_access_point_id="published-access",
            duration_min=30, duration_recommended=90, duration_max=120,
            internal_travel_min=5, solver_payload={"name": "数据库发布景点"},
            projection_hash="a" * 64, status="published", gate_reason_codes=[],
            created_at="2026-08-30T00:00:00+00:00", published_at="2026-08-30T00:00:00+00:00",
        ))
        session.commit()

    client = TestClient(build_local_dev_app(database_url=database_url, reference_date=date(2026, 8, 25)))
    token = client.post("/api/v1/anonymous-sessions", json={}).json()["access_token"]
    response = client.get("/api/v1/attractions", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["data_snapshot_version"].startswith("database-hangzhou-")
    assert body["items"] == [{
        "attraction_id": "published-place", "name": "数据库发布景点",
        "suggested_duration_min": 90, "is_always_open": True, "is_indoor": False,
        "energy_level": 2, "close_days": [], "coordinate": {"lat": 30.25, "lng": 120.16},
    }]
