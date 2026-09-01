"""Published solver data backed by the place-catalog database.

The local HTTP composition uses this adapter before its deterministic fixture.
Only rows that passed the publication gate are exposed to anonymous users.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    Coordinate,
    DailyWeather,
    TimeRule,
    WeatherBasis,
    WeatherSeverity,
)

from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceRow,
    PlaceRevisionRow,
    PlaceTimeRuleRow,
    SolverPlaceProjectionRow,
)

from .gateway import PublishedAttraction, PublishedSolverData, PublishedSolverDataProvider


class DatabasePublishedSnapshotVersionProvider:
    """Resolve the latest published research snapshot for a city."""

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        fallback_version: str,
    ) -> None:
        self._sessions = sessions
        self._fallback_version = fallback_version

    def current_version(self, city_id: str) -> str:
        try:
            with self._sessions() as session:
                projections = _latest_published_projections(session, city_id)
                return (
                    _database_catalog_version(city_id, projections)
                    if projections
                    else self._fallback_version
                )
        except SQLAlchemyError:
            return self._fallback_version


class DatabasePublishedSolverDataProvider:
    """Build ``PublishedSolverData`` from currently published catalog rows.

    A fallback provider is deliberately injected for an empty local database;
    production composition should use the strict JSON provider instead.
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        *,
        city_id: str,
        fallback: PublishedSolverDataProvider,
        fallback_version: str = "hangzhou-local-v1",
        weather_factory: Callable[[date], dict[date, DailyWeather]] | None = None,
    ) -> None:
        self._sessions = sessions
        self._city_id = city_id
        self._fallback = fallback
        self._fallback_version = fallback_version
        self._weather_factory = weather_factory or _local_weather
        self._cache: dict[str, PublishedSolverData] = {}

    def load(self, version: str) -> PublishedSolverData:
        cached = self._cache.get(version)
        if cached is not None:
            return cached
        if version == self._fallback_version:
            loaded = self._fallback.load(version)
            self._cache[version] = loaded
            return loaded
        try:
            loaded = self._load_database(version)
        except (SQLAlchemyError, ValueError) as exc:
            raise LookupError("database published catalog unavailable") from exc
        self._cache[version] = loaded
        return loaded

    def _load_database(self, version: str) -> PublishedSolverData:
        with self._sessions() as session:
            projections = _latest_published_projections(session, self._city_id)
            if not projections:
                raise LookupError("no published projections")
            if _database_catalog_version(self._city_id, projections) != version:
                raise LookupError("database published catalog version is no longer current")
            attractions: list[PublishedAttraction] = []
            coordinates: dict[int, Coordinate] = {}
            for solver_node_id, projection in enumerate(projections, start=1):
                revision = session.get(PlaceRevisionRow, projection.place_revision_id)
                if revision is None:
                    continue
                access_rows = tuple(
                    session.scalars(
                        select(PlaceAccessPointRow)
                        .where(
                            PlaceAccessPointRow.place_revision_id == revision.place_revision_id,
                            PlaceAccessPointRow.active.is_(True),
                            PlaceAccessPointRow.review_status == "human_verified",
                        )
                    )
                )
                by_id = {row.access_point_id: row for row in access_rows}
                arrival = by_id.get(projection.arrival_access_point_id) or (access_rows[0] if access_rows else None)
                if arrival is None:
                    continue
                coordinate = Coordinate(float(arrival.lat), float(arrival.lng))
                coordinates[solver_node_id] = coordinate
                payload = projection.solver_payload or {}
                name = str(payload.get("name") or revision.canonical_name)
                duration = int(payload.get("suggested_duration") or revision.duration_recommended)
                rules = _time_rules(session, revision.place_revision_id)
                attraction = Attraction(
                    solver_node_id,
                    name,
                    close_days=frozenset(_close_days(session, revision.place_revision_id)),
                    suggested_duration=duration,
                    time_rules=rules,
                    is_always_open=revision.is_always_open,
                    is_indoor=revision.indoor_outdoor == "indoor",
                    energy_level=revision.energy_level,
                    data_verified=True,
                )
                attractions.append(PublishedAttraction(revision.place_id, attraction, coordinate))
            if not attractions:
                raise LookupError("published projections have no usable access points")
            today = date.today()
            return PublishedSolverData(
                version=version,
                city_id=self._city_id,
                attractions=tuple(attractions),
                weather_by_date=self._weather_factory(today),
                travel_time_provider=ApproximateTravelTimeProvider(
                    coordinates,
                    speed_kmh=18,
                    detour_ratio=1.6,
                    minimum_travel_min=5,
                    data_version="database-published-approx-od-v1",
                    fetched_at=datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                ),
                od_basis="database_published_approximate",
                weather_basis="deterministic_local_fixture",
            )


def _time_rules(session: Session, revision_id: str) -> tuple[TimeRule, ...]:
    rows = tuple(
        session.scalars(
            select(PlaceTimeRuleRow)
            .where(
                PlaceTimeRuleRow.place_revision_id == revision_id,
                PlaceTimeRuleRow.active.is_(True),
                PlaceTimeRuleRow.review_status == "human_verified",
            )
            .order_by(PlaceTimeRuleRow.created_at.asc(), PlaceTimeRuleRow.time_rule_id.asc())
        )
    )
    # The solver's recurring rule is date-range based.  Published weekly rows
    # with identical hours are therefore collapsed into one year-wide rule.
    unique = {(row.start_minute, row.end_minute, row.last_entry_minute) for row in rows}
    result: list[TimeRule] = []
    for start, end, last_entry in sorted(
        unique,
        key=lambda value: tuple(-1 if item is None else item for item in value),
    ):
        if start is None or end is None:
            continue
        result.append(
            TimeRule.from_strings(
                ("01-01", "12-31"),
                _clock(start),
                _clock(end),
                _clock(last_entry) if last_entry is not None else None,
                crosses_midnight=end >= 1440,
            )
        )
    return tuple(result)


def _close_days(session: Session, revision_id: str) -> tuple[int, ...]:
    from travel_agent.infrastructure.database.place_catalog import PlaceClosureRow

    return tuple(
        row.weekday
        for row in session.scalars(
            select(PlaceClosureRow).where(
                PlaceClosureRow.place_revision_id == revision_id,
                PlaceClosureRow.active.is_(True),
                PlaceClosureRow.review_status == "human_verified",
            )
        )
    )


def _clock(minutes: int) -> str:
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _local_weather(today: date) -> dict[date, DailyWeather]:
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, WeatherSeverity.NORMAL, "local deterministic normal weather")
        for offset in range(-30, 401)
        for day in (today + timedelta(days=offset),)
    }


def _latest_published_projections(
    session: Session,
    city_id: str,
) -> tuple[SolverPlaceProjectionRow, ...]:
    rows = tuple(
        session.scalars(
            select(SolverPlaceProjectionRow)
            .join(
                PlaceRevisionRow,
                PlaceRevisionRow.place_revision_id
                == SolverPlaceProjectionRow.place_revision_id,
            )
            .join(PlaceRow, PlaceRow.place_id == SolverPlaceProjectionRow.place_id)
            .where(
                SolverPlaceProjectionRow.status == "published",
                PlaceRevisionRow.lifecycle_status == "published",
                PlaceRevisionRow.place_id == SolverPlaceProjectionRow.place_id,
                PlaceRow.city_id == city_id,
                PlaceRow.status == "active",
            )
            .order_by(
                SolverPlaceProjectionRow.place_id.asc(),
                SolverPlaceProjectionRow.published_at.desc(),
                PlaceRevisionRow.revision_number.desc(),
                SolverPlaceProjectionRow.projection_id.desc(),
            )
        )
    )
    latest: dict[str, SolverPlaceProjectionRow] = {}
    for row in rows:
        latest.setdefault(row.place_id, row)
    return tuple(
        sorted(
            latest.values(),
            key=lambda row: (row.solver_node_id, row.place_id, row.projection_id),
        )
    )


def _database_catalog_version(
    city_id: str,
    projections: tuple[SolverPlaceProjectionRow, ...],
) -> str:
    payload = [
        {
            "projection_id": row.projection_id,
            "projection_hash": row.projection_hash,
            "published_at": row.published_at,
        }
        for row in projections
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:20]
    return f"database-{city_id}-{digest}"
