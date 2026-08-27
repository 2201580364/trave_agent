"""Environment-driven production composition for immutable published data."""

from __future__ import annotations

import os
from dataclasses import dataclass
from os import PathLike
from pathlib import Path
from typing import cast

from fastapi import FastAPI

from travel_agent.infrastructure.database import DatabaseSettings
from travel_agent.infrastructure.memory import FixedDataSnapshotVersionProvider
from travel_agent.infrastructure.solver import JsonPublishedSolverDataProvider
from travel_agent.runtime_config import load_runtime_environment

from .composition import HttpSettings, build_http_app


@dataclass(frozen=True, slots=True)
class PublishedSnapshotSettings:
    """Select the single M1 city snapshot exposed by this process."""

    root: Path
    city_id: str
    version: str

    def __post_init__(self) -> None:
        if not self.city_id:
            raise ValueError("published snapshot city id is required")
        if not self.version:
            raise ValueError("published snapshot version is required")

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
        if not root:
            raise ValueError("TRAVEL_AGENT_PUBLISHED_SNAPSHOT_ROOT is required")
        root_path = Path(root)
        if not root_path.is_absolute() and relative_to is not None:
            root_path = relative_to / root_path
        return cls(root_path.resolve(), city_id, version)


@dataclass(frozen=True, slots=True)
class ProductionHttpSettings:
    database: DatabaseSettings
    published_snapshot: PublishedSnapshotSettings

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
    ) -> ProductionHttpSettings:
        loaded = load_runtime_environment(dotenv_path)
        return cls(
            DatabaseSettings.from_env(load_dotenv_file=False),
            PublishedSnapshotSettings.from_env(
                load_dotenv_file=False,
                relative_to=loaded.resolve().parent if loaded is not None else None,
            ),
        )


def build_production_http_app(settings: ProductionHttpSettings) -> FastAPI:
    """Build the HTTP application and fail fast on unpublished solver data."""

    published_data = JsonPublishedSolverDataProvider(
        settings.published_snapshot.root,
    )
    selected = published_data.load(settings.published_snapshot.version)
    if selected.city_id != settings.published_snapshot.city_id:
        raise ValueError("published solver snapshot city mismatch")
    versions = FixedDataSnapshotVersionProvider(
        {settings.published_snapshot.city_id: settings.published_snapshot.version}
    )
    return cast(
        FastAPI,
        build_http_app(
            HttpSettings(settings.database),
            versions,
            published_data,
        ),
    )
