"""A6-6.5 database configuration and MySQL dialect compatibility tests."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from travel_agent.infrastructure.database import (
    Base,
    DatabaseReadiness,
    DatabaseSettings,
    build_engine,
    build_session_factory,
    create_schema,
)


def test_database_settings_load_pool_values_without_repr_secret(monkeypatch) -> None:
    monkeypatch.setenv(
        "TRAVEL_AGENT_DATABASE_URL",
        "mysql+pymysql://app_user:secret@example.invalid/travel_agent",
    )
    monkeypatch.setenv("TRAVEL_AGENT_DB_POOL_SIZE", "8")
    monkeypatch.setenv("TRAVEL_AGENT_DB_MAX_OVERFLOW", "12")

    settings = DatabaseSettings.from_env(load_dotenv_file=False)

    assert settings.pool_size == 8
    assert settings.max_overflow == 12
    assert "secret" not in repr(settings)


def test_mysql_engine_and_metadata_use_pymysql_innodb_utf8mb4_and_json() -> None:
    settings = DatabaseSettings(
        "mysql+pymysql://app_user:secret@example.invalid/travel_agent"
    )
    engine = build_engine(settings)

    ddl = "\n".join(
        str(CreateTable(table).compile(dialect=mysql.dialect()))
        for table in Base.metadata.sorted_tables
    )

    assert engine.dialect.name == "mysql"
    assert "secret" not in engine.url.render_as_string(hide_password=True)
    assert "ENGINE=InnoDB" in ddl
    assert "CHARSET=utf8mb4" in ddl
    assert "COLLATE utf8mb4_0900_ai_ci" in ddl
    assert "JSON" in ddl


def test_readiness_distinguishes_database_from_migration_state(tmp_path: Path) -> None:
    database = tmp_path / "readiness.db"
    engine = create_engine(f"sqlite:///{database}")
    create_schema(engine)
    readiness = DatabaseReadiness(build_session_factory(engine))

    before = readiness.check()

    assert before["database"] is True
    assert before["migration"] is False
    assert before["ready"] is False

    migrated = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.attributes["skip_dotenv"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{migrated}")
    command.upgrade(config, "head")
    migrated_engine = create_engine(f"sqlite:///{migrated}")

    after = DatabaseReadiness(build_session_factory(migrated_engine)).check()

    assert after["database"] is True
    assert after["migration"] is True
    assert after["ready"] is True
    assert after["current_revision"] == "0012_relation_review_status"
