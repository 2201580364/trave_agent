"""Environment-driven production composition for immutable published data."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from os import PathLike
from pathlib import Path
from typing import cast

from fastapi import FastAPI

from travel_agent.infrastructure.database import DatabaseSettings
from travel_agent.infrastructure.memory import FixedDataSnapshotVersionProvider
from travel_agent.infrastructure.solver import JsonPublishedSolverDataProvider
from travel_agent.runtime_config import load_runtime_environment

from .composition import HttpSettings, build_http_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PublishedSnapshotSettings:
    """Select the single M1 city snapshot exposed by this process."""

    root: Path
    city_id: str
    version: str
    fallback_versions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.city_id:
            raise ValueError("published snapshot city id is required")
        if not self.version:
            raise ValueError("published snapshot version is required")
        if any(not item.strip() for item in self.fallback_versions):
            raise ValueError("published snapshot fallback versions must be non-empty")
        versions = (self.version, *self.fallback_versions)
        if len(set(versions)) != len(versions):
            raise ValueError("published snapshot versions must be unique")

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
        load_dotenv_file: bool = True,
        relative_to: Path | None = None,
    ) -> PublishedSnapshotSettings:
        if load_dotenv_file:
            loaded = load_runtime_environment(dotenv_path)
            if loaded is not None:
                relative_to = loaded.resolve().parent
        root = os.environ.get("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT", "").strip()
        city_id = os.environ.get("TRAVEL_AGENT_PUBLISHED_CITY_ID", "").strip()
        version = os.environ.get("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_VERSION", "").strip()
        fallback_versions = tuple(
            item.strip()
            for item in os.environ.get(
                "TRAVEL_AGENT_PUBLISHED_SNAPSHOT_FALLBACK_VERSIONS",
                "",
            ).split(",")
            if item.strip()
        )
        if not root:
            raise ValueError("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT is required")
        root_path = Path(root)
        if not root_path.is_absolute() and relative_to is not None:
            root_path = relative_to / root_path
        return cls(root_path.resolve(), city_id, version, fallback_versions)


@dataclass(frozen=True, slots=True)
class ProductionHttpSettings:
    database: DatabaseSettings
    published_snapshot: PublishedSnapshotSettings
    plan_share_token_secret: str
    admin_bootstrap_login: str | None = None
    admin_bootstrap_password: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
    ) -> ProductionHttpSettings:
        loaded = load_runtime_environment(dotenv_path)
        secret = os.environ.get("TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ValueError(
                "TRAVEL_AGENT_PLAN_SHARE_TOKEN_SECRET must contain at least 32 bytes"
            )
        admin_login = os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN", "").strip()
        admin_password = os.environ.get("TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD", "")
        if bool(admin_login) != bool(admin_password):
            raise ValueError(
                "TRAVEL_AGENT_ADMIN_BOOTSTRAP_LOGIN and "
                "TRAVEL_AGENT_ADMIN_BOOTSTRAP_PASSWORD must be configured together"
            )
        return cls(
            DatabaseSettings.from_env(load_dotenv_file=False),
            PublishedSnapshotSettings.from_env(
                load_dotenv_file=False,
                relative_to=loaded.resolve().parent if loaded is not None else None,
            ),
            secret,
            admin_login or None,
            admin_password or None,
        )


def build_production_http_app(settings: ProductionHttpSettings) -> FastAPI:
    """Build the HTTP application from a current or explicit fallback snapshot."""

    published_data = JsonPublishedSolverDataProvider(
        settings.published_snapshot.root,
    )
    selected = None
    failures: list[str] = []
    requested_versions = (
        settings.published_snapshot.version,
        *settings.published_snapshot.fallback_versions,
    )
    for version in requested_versions:
        try:
            candidate = published_data.load(version)
            if candidate.city_id != settings.published_snapshot.city_id:
                raise ValueError(f"published solver snapshot city mismatch: {version}")
        except (LookupError, ValueError) as exc:
            failures.append(str(exc))
            continue
        selected = candidate
        break
    if selected is None:
        detail = "; ".join(failures)
        raise ValueError(f"no valid published solver snapshot is available: {detail}")
    fallback_used = selected.version != settings.published_snapshot.version
    if fallback_used:
        logger.error(
            "published snapshot fallback activated",
            extra={
                "component": "http.production",
                "requested_snapshot_version": settings.published_snapshot.version,
                "selected_snapshot_version": selected.version,
            },
        )
    snapshot_versions = FixedDataSnapshotVersionProvider(
        {settings.published_snapshot.city_id: selected.version}
    )
    app = cast(
        FastAPI,
        build_http_app(
            HttpSettings(
                settings.database,
                settings.plan_share_token_secret,
                settings.admin_bootstrap_login,
                settings.admin_bootstrap_password,
            ),
            snapshot_versions,
            published_data,
        ),
    )
    app.state.published_snapshot_requested_version = settings.published_snapshot.version
    app.state.published_snapshot_selected_version = selected.version
    app.state.published_snapshot_fallback_used = fallback_used
    return app
