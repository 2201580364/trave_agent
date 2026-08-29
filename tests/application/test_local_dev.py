"""A6-7 local browser-validation composition tests. Traceability: H3."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from travel_agent.local_dev import build_local_dev_app, build_local_hangzhou_catalog


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
