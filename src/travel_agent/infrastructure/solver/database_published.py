"""Published solver data backed by the place-catalog database.

The local HTTP composition uses this adapter before its deterministic fixture.
Only rows that passed the publication gate are exposed to anonymous users.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from travel_agent.infrastructure.database.place_catalog import (
    PlaceAccessPointRow,
    PlaceRevisionRow,
    PlaceRow,
    PlaceTimeRuleRow,
    SelectionExclusionGroupRow,
    SelectionExclusionMemberRow,
    SolverPlaceProjectionRow,
    SqlAlchemyPlaceCatalogRepository,
)
from travel_agent.solver import (
    ApproximateTravelTimeProvider,
    Attraction,
    Coordinate,
    DailyWeather,
    FixedSession,
    TimeRule,
    WeatherBasis,
    WeatherSeverity,
)

from .fixed_sessions import parse_fixed_sessions
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
            departure_coordinates: dict[int, Coordinate] = {}
            for solver_node_id, projection in enumerate(projections, start=1):
                revision = session.get(PlaceRevisionRow, projection.place_revision_id)
                if revision is None:
                    continue
                access_rows = tuple(
                    session.scalars(
                        select(PlaceAccessPointRow).where(
                            PlaceAccessPointRow.place_revision_id == revision.place_revision_id,
                            PlaceAccessPointRow.active.is_(True),
                            PlaceAccessPointRow.review_status == "human_verified",
                        )
                    )
                )
                by_id = {row.access_point_id: row for row in access_rows}
                arrival = by_id.get(projection.arrival_access_point_id)
                departure = by_id.get(projection.departure_access_point_id)
                if arrival is None or departure is None:
                    continue
                coordinate = Coordinate(float(arrival.lat), float(arrival.lng))
                coordinates[solver_node_id] = coordinate
                departure_coordinates[solver_node_id] = Coordinate(
                    float(departure.lat), float(departure.lng)
                )
                payload = projection.solver_payload or {}
                name = str(payload.get("name") or revision.canonical_name)
                duration = int(payload.get("suggested_duration") or revision.duration_recommended)
                rules = (
                    ()
                    if revision.place_kind == "show"
                    else _time_rules(session, revision.place_revision_id)
                )
                fixed_sessions: tuple[FixedSession, ...] = ()
                if (
                    revision.place_kind == "show"
                    or session.scalar(
                        select(PlaceTimeRuleRow.time_rule_id)
                        .where(
                            PlaceTimeRuleRow.place_revision_id == revision.place_revision_id,
                            PlaceTimeRuleRow.rule_kind == "fixed_session",
                            PlaceTimeRuleRow.active.is_(True),
                            PlaceTimeRuleRow.review_status == "human_verified",
                        )
                        .limit(1)
                    )
                    is not None
                ):
                    from travel_agent.domain.place_catalog.session_payload import (
                        build_fixed_session_payload,
                    )

                    session_payload = payload.get("fixed_sessions")
                    if session_payload is None:
                        evidence = SqlAlchemyPlaceCatalogRepository(session).load_revision_evidence(
                            revision.place_revision_id
                        )
                        if evidence is None:
                            raise ValueError("show evidence is missing")
                        session_payload = build_fixed_session_payload(evidence)
                    try:
                        fixed_sessions = parse_fixed_sessions(session_payload)
                    except ValueError:
                        # Keep the public catalog available when an old
                        # projection contains invalid show timing data. The
                        # revision remains visible to reviewers and is
                        # excluded from solver eligibility until corrected.
                        continue
                    if not fixed_sessions:
                        raise ValueError("published show requires a fixed session")
                attraction = Attraction(
                    solver_node_id,
                    name,
                    close_days=frozenset(_close_days(session, revision.place_revision_id)),
                    open_on_dates=frozenset(
                        _exception_dates(session, revision.place_revision_id, "open_override")
                        + _exception_dates(session, revision.place_revision_id, "session_override")
                    ),
                    closed_on_dates=frozenset(
                        _exception_dates(session, revision.place_revision_id, "closed")
                    ),
                    suggested_duration=duration,
                    time_rules=rules,
                    is_always_open=revision.is_always_open,
                    is_indoor=revision.indoor_outdoor == "indoor",
                    energy_level=revision.energy_level,
                    data_verified=True,
                    fixed_sessions=fixed_sessions,
                )
                attractions.append(PublishedAttraction(revision.place_id, attraction, coordinate))
            if not attractions:
                raise LookupError("published projections have no usable access points")
            exclusion_groups = _selection_exclusion_groups(
                session,
                self._city_id,
                {item.external_id: item.external_id for item in attractions},
            )
            if exclusion_groups:
                attractions = [
                    PublishedAttraction(
                        item.external_id,
                        item.attraction,
                        item.coordinate,
                        tuple(sorted(exclusion_groups.get(item.external_id, ()))),
                    )
                    for item in attractions
                ]
            today = date.today()
            return PublishedSolverData(
                version=version,
                city_id=self._city_id,
                attractions=tuple(attractions),
                weather_by_date=self._weather_factory(today),
                travel_time_provider=ApproximateTravelTimeProvider(
                    coordinates,
                    departure_coordinates=departure_coordinates,
                    speed_kmh=18,
                    walking_threshold_m=2000,
                    walking_speed_kmh=4.5,
                    detour_ratio=1.6,
                    minimum_travel_min=5,
                    data_version="database-published-approx-od-v2",
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
    # Preserve evidence kind and calendar applicability. Fixed departures are
    # loaded as discrete sessions, never flattened into opening hours (H3/C2).
    return tuple(
        TimeRule(
            1,
            1,
            12,
            31,
            row.start_minute,
            row.end_minute,
            row.last_entry_minute,
            frozenset(row.weekdays),
            row.valid_from,
            row.valid_to,
        )
        for row in rows
        if row.rule_kind == "opening_hours"
        and row.start_minute is not None
        and row.end_minute is not None
    )


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


def _exception_dates(session: Session, revision_id: str, kind: str) -> tuple[date, ...]:
    from travel_agent.infrastructure.database.place_catalog import PlaceDateExceptionRow

    return tuple(
        row.service_date
        for row in session.scalars(
            select(PlaceDateExceptionRow).where(
                PlaceDateExceptionRow.place_revision_id == revision_id,
                PlaceDateExceptionRow.exception_kind == kind,
                PlaceDateExceptionRow.active.is_(True),
                PlaceDateExceptionRow.review_status == "human_verified",
            )
        )
    )


def _selection_exclusion_groups(
    session: Session,
    city_id: str,
    place_by_external_id: dict[str, str],
) -> dict[str, set[str]]:
    """Load only reviewed active selection groups for the current catalog.

    Relation rows are evidence; an exclusion group is the reviewed, explicit
    solver decision that turns an overlap/same-experience relation into a
    hard selection constraint.  Candidate or retired groups never enter a
    published solver snapshot.
    """
    rows = tuple(
        session.execute(
            select(SelectionExclusionMemberRow, SelectionExclusionGroupRow)
            .join(
                SelectionExclusionGroupRow,
                SelectionExclusionGroupRow.exclusion_group_id
                == SelectionExclusionMemberRow.exclusion_group_id,
            )
            .where(
                SelectionExclusionGroupRow.city_id == city_id,
                SelectionExclusionGroupRow.status == "active",
                SelectionExclusionGroupRow.review_status == "human_verified",
            )
        )
    )
    place_to_external = {
        place_id: external_id for external_id, place_id in place_by_external_id.items()
    }
    result: dict[str, set[str]] = {}
    for member, group in rows:
        external_id = place_to_external.get(member.place_id)
        if external_id is not None:
            result.setdefault(external_id, set()).add(group.exclusion_group_id)
    return result


def _local_weather(today: date) -> dict[date, DailyWeather]:
    note = "local deterministic normal weather"
    return {
        day: DailyWeather(day, WeatherBasis.FORECAST, WeatherSeverity.NORMAL, note)
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
                PlaceRevisionRow.place_revision_id == SolverPlaceProjectionRow.place_revision_id,
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
