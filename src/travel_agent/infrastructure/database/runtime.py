"""Environment-driven database engine and readiness configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from os import PathLike

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.runtime_config import load_runtime_environment

EXPECTED_ALEMBIC_REVISION = "0002_anonymous_identity"


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str = field(repr=False)
    echo_sql: bool = False
    pool_size: int = 5
    max_overflow: int = 10
    pool_recycle_seconds: int = 1800
    pool_timeout_seconds: int = 30

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
        load_dotenv_file: bool = True,
    ) -> DatabaseSettings:
        if load_dotenv_file:
            load_runtime_environment(dotenv_path)
        url = os.environ.get("TRAVEL_AGENT_DATABASE_URL", "").strip()
        if not url:
            raise ValueError("TRAVEL_AGENT_DATABASE_URL is required")
        return cls(
            url=url,
            echo_sql=_env_bool("TRAVEL_AGENT_DATABASE_ECHO", False),
            pool_size=_env_int("TRAVEL_AGENT_DB_POOL_SIZE", 5, minimum=1),
            max_overflow=_env_int("TRAVEL_AGENT_DB_MAX_OVERFLOW", 10, minimum=0),
            pool_recycle_seconds=_env_int(
                "TRAVEL_AGENT_DB_POOL_RECYCLE_SECONDS", 1800, minimum=1
            ),
            pool_timeout_seconds=_env_int(
                "TRAVEL_AGENT_DB_POOL_TIMEOUT_SECONDS", 30, minimum=1
            ),
        )


def build_engine(settings: DatabaseSettings) -> Engine:
    common: dict[str, object] = {
        "echo": settings.echo_sql,
        "pool_pre_ping": True,
    }
    if settings.url.startswith("sqlite"):
        common["connect_args"] = {"check_same_thread": False}
    else:
        common.update(
            {
                "pool_size": settings.pool_size,
                "max_overflow": settings.max_overflow,
                "pool_recycle": settings.pool_recycle_seconds,
                "pool_timeout": settings.pool_timeout_seconds,
            }
        )
        if settings.url.startswith("mysql+pymysql"):
            common["connect_args"] = {"charset": "utf8mb4"}
            common["isolation_level"] = "READ COMMITTED"
    return create_engine(settings.url, **common)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker[Session](engine, expire_on_commit=False)


class DatabaseReadiness:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        expected_revision: str = EXPECTED_ALEMBIC_REVISION,
    ) -> None:
        self._sessions = sessions
        self._expected_revision = expected_revision

    def check(self) -> dict[str, object]:
        try:
            with self._sessions() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            return {"ready": False, "database": False, "migration": False}
        try:
            with self._sessions() as session:
                revision = session.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one_or_none()
        except Exception:
            return {
                "ready": False,
                "database": True,
                "migration": False,
                "current_revision": None,
                "expected_revision": self._expected_revision,
            }
        return {
            "ready": revision == self._expected_revision,
            "database": True,
            "migration": revision == self._expected_revision,
            "current_revision": revision,
            "expected_revision": self._expected_revision,
        }


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.environ.get(name)
    value = default if raw is None else int(raw)
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value
