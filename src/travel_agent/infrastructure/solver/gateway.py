"""Production adapter for the stable, versioned M1 deterministic solver contract."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from enum import Enum
from fractions import Fraction
from time import perf_counter
from typing import Protocol

from travel_agent.application.common.clock import Clock
from travel_agent.application.planning.ports import (
    SolverExecutionError,
    SolverOutcome,
    SolverRequest,
)
from travel_agent.domain.planning import CompletionKind
from travel_agent.observability.solver_audit import build_solver_run_audit
from travel_agent.solver import (
    CONSTRAINT_VERSION,
    DEFAULT_OD_DURATION_REBALANCE_MAX_SYMMETRIC_PENALTY_MIN,
    PARAMETER_VERSION,
    SOLVER_CONTRACT_VERSION,
    Attraction,
    AttractionPreference,
    Coordinate,
    DailyWeather,
    TimeBucket,
    TravelMode,
    TravelTimeProvider,
    TravelTimeResult,
    TripTimeAnchors,
    VisitPeriodPreference,
    VisitPeriodPreferenceSource,
    assign_days,
    evaluate_itinerary_degradation,
    evaluate_solver_quality,
    resolve_day_time_bounds,
    resolve_effective_window,
    route_itinerary,
)

LUNCH_EARLIEST_MIN = 11 * 60 + 30
LUNCH_LATEST_END_MIN = 14 * 60
LUNCH_FULL_DURATION_MIN = 60
LUNCH_REDUCED_DURATION_MIN = 30


@dataclass(frozen=True, slots=True)
class PublishedAttraction:
    external_id: str
    attraction: Attraction
    coordinate: Coordinate | None = None


@dataclass(frozen=True, slots=True)
class PublishedSolverData:
    version: str
    city_id: str
    attractions: tuple[PublishedAttraction, ...]
    weather_by_date: dict[date, DailyWeather]
    travel_time_provider: TravelTimeProvider
    od_basis: str
    weather_basis: str

    def __post_init__(self) -> None:
        external_ids = [item.external_id for item in self.attractions]
        solver_ids = [item.attraction.id for item in self.attractions]
        if len(set(external_ids)) != len(external_ids):
            raise ValueError("published attraction external ids must be unique")
        if len(set(solver_ids)) != len(solver_ids):
            raise ValueError("published attraction solver ids must be unique")


class PublishedSolverDataProvider(Protocol):
    def load(self, version: str) -> PublishedSolverData: ...


class InMemoryPublishedSolverDataProvider:
    def __init__(self, snapshots: tuple[PublishedSolverData, ...]) -> None:
        self._snapshots = {item.version: item for item in snapshots}

    def load(self, version: str) -> PublishedSolverData:
        try:
            return self._snapshots[version]
        except KeyError as exc:
            raise LookupError(f"published solver snapshot not found: {version}") from exc


class ProductionSolverGateway:
    def __init__(self, data: PublishedSolverDataProvider, clock: Clock) -> None:
        self._data = data
        self._clock = clock

    def solve(self, request: SolverRequest) -> SolverOutcome:
        started = perf_counter()
        try:
            snapshot = self._data.load(request.data_snapshot_version)
        except LookupError as exc:
            raise SolverExecutionError("data_snapshot_unavailable", retryable=True) from exc
        try:
            if _stable_hash(request.input_snapshot) != request.input_snapshot_hash:
                raise ValueError("generation input snapshot hash does not match")
            prepared = _prepare_input(request.input_snapshot, snapshot)
            step1 = assign_days(
                prepared.preferences,
                trip_dates=prepared.trip_dates,
                weather_by_date=prepared.weather,
                anchors=prepared.anchors,
                travel_mode=prepared.travel_mode,
            )
            itinerary = route_itinerary(
                step1,
                snapshot.travel_time_provider,
                weather_by_date=prepared.weather,
            )
            quality = evaluate_solver_quality(itinerary, prepared.attractions)
            degradation = evaluate_itinerary_degradation(
                itinerary,
                quality,
                input_count=len(prepared.attractions),
                day_count=len(prepared.trip_dates),
            )
            elapsed_ms = max(0, int((perf_counter() - started) * 1000))
            result = _result_snapshot(
                request, snapshot, itinerary, quality, degradation
            )
            audit = build_solver_run_audit(
                itinerary,
                quality,
                solve_run_id=request.solver_run_id,
                solver_version=SOLVER_CONTRACT_VERSION,
                constraint_version=CONSTRAINT_VERSION,
                parameter_version=PARAMETER_VERSION,
                input_snapshot_hash=request.input_snapshot_hash,
                data_snapshot_version=request.data_snapshot_version,
                od_basis=snapshot.od_basis,
                weather_basis=snapshot.weather_basis,
                random_seed=request.random_seed,
                duration_ratio=_duration_ratio(prepared.travel_mode),
                elapsed_ms=elapsed_ms,
                created_at=self._clock.now(),
            )
            partial = bool(itinerary.unplaced or itinerary.data_rejected)
            completion = (
                CompletionKind.PARTIAL_SUCCESS
                if partial
                else CompletionKind.COMPLETE_SUCCESS
            )
            return SolverOutcome(
                completion,
                bool(degradation.notices),
                quality.gate_passed,
                "trip-result-v2",
                result,
                _stable_hash(result),
                SOLVER_CONTRACT_VERSION,
                CONSTRAINT_VERSION,
                PARAMETER_VERSION,
                audit.to_dict(),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SolverExecutionError("invalid_solver_input", retryable=False) from exc
        except SolverExecutionError:
            raise
        except Exception as exc:
            raise SolverExecutionError("solver_execution_failed", retryable=True) from exc


@dataclass(frozen=True, slots=True)
class _PreparedInput:
    attractions: tuple[Attraction, ...]
    preferences: tuple[AttractionPreference, ...]
    trip_dates: tuple[date, ...]
    weather: dict[date, DailyWeather]
    anchors: TripTimeAnchors
    travel_mode: TravelMode


def _prepare_input(
    input_snapshot: dict[str, object], published: PublishedSolverData
) -> _PreparedInput:
    if input_snapshot.get("schema_version") != "generation-input-v1":
        raise ValueError("unsupported generation input schema")
    if input_snapshot.get("data_snapshot_version") != published.version:
        raise ValueError("input and published data versions do not match")
    if input_snapshot.get("city_id") != published.city_id:
        raise ValueError("input and published city do not match")
    facts = _mapping(input_snapshot["travel_facts"])
    start_date = date.fromisoformat(_text(facts["start_date"]))
    end_date = date.fromisoformat(_text(facts["end_date"]))
    trip_dates = tuple(
        start_date + timedelta(days=offset)
        for offset in range((end_date - start_date).days + 1)
    )
    arrival = datetime.fromisoformat(_text(facts["arrival_at"]))
    departure = datetime.fromisoformat(_text(facts["departure_at"]))
    anchors = TripTimeAnchors(
        _minute_of_day(arrival),
        int(facts["station_to_city_min"]),
        _minute_of_day(departure),
        int(facts["station_early_min"]),
        int(facts["last_visit_to_station_min"]),
    )
    travel_mode = TravelMode(_text(facts["travel_mode"]))
    by_external_id = {item.external_id: item.attraction for item in published.attractions}
    selected_ids = tuple(
        _text(item) for item in _list(input_snapshot["selected_attraction_ids"])
    )
    attractions = tuple(by_external_id[item] for item in selected_ids)
    preferred_dates = _balanced_default_preferred_dates(
        attractions,
        trip_dates,
        anchors,
        published.travel_time_provider,
    )
    preference_inputs = {
        _text(item["attraction_id"]): item
        for raw in _list(input_snapshot.get("visit_period_preferences", []))
        for item in (_mapping(raw),)
    }
    preferences = tuple(
        AttractionPreference(
            attraction,
            preferred_dates[attraction.id],
            _visit_period(preference_inputs.get(external_id)),
        )
        for external_id, attraction in zip(selected_ids, attractions, strict=True)
    )
    weather = {day: published.weather_by_date[day] for day in trip_dates}
    return _PreparedInput(attractions, preferences, trip_dates, weather, anchors, travel_mode)


def _balanced_default_preferred_dates(
    attractions: tuple[Attraction, ...],
    trip_dates: tuple[date, ...],
    anchors: TripTimeAnchors,
    travel_time_provider: TravelTimeProvider,
) -> dict[int, date]:
    """Derive stable, OD-aware neutral dates when users do not choose dates.

    The public generation input currently carries visit-period preferences but no
    attraction-level date preference. Attractions are first grouped by the
    symmetric cost of the published directed OD snapshot, with a deterministic
    maximum cluster size. The resulting nearby groups are then balanced across
    usable C4 capacity. Step 1 remains responsible for opening-day, weather and
    time-window feasibility and may reassign an attraction when necessary.
    """

    capacities: dict[date, int] = {}
    for day_index, visit_date in enumerate(trip_dates, start=1):
        resolution = resolve_day_time_bounds(
            day_index=day_index,
            total_days=len(trip_dates),
            anchors=anchors,
        )
        if resolution.bounds is not None:
            capacity = resolution.bounds.end_min - resolution.bounds.start_min
            if capacity > 0:
                capacities[visit_date] = capacity

    if not capacities:
        return {attraction.id: trip_dates[0] for attraction in attractions}

    cluster_count = min(len(capacities), len(attractions))
    clusters = _cluster_attractions_by_od(
        attractions,
        cluster_count,
        travel_time_provider,
    )
    assigned_duration = {visit_date: 0 for visit_date in capacities}
    assigned_energy = {visit_date: 0 for visit_date in capacities}
    assigned_count = {visit_date: 0 for visit_date in capacities}
    preferred_dates: dict[int, date] = {}

    ordered_clusters = sorted(
        clusters,
        key=lambda cluster: (
            -sum(item.suggested_duration for item in cluster),
            -sum(item.energy_level for item in cluster),
            tuple(item.id for item in cluster),
        ),
    )
    for cluster in ordered_clusters:
        cluster_duration = sum(item.suggested_duration for item in cluster)
        cluster_energy = sum(item.energy_level for item in cluster)
        cluster_size = len(cluster)
        selected_date = min(
            capacities,
            key=lambda visit_date: (
                Fraction(
                    assigned_duration[visit_date] + cluster_duration,
                    capacities[visit_date],
                ),
                assigned_energy[visit_date] + cluster_energy,
                assigned_count[visit_date] + cluster_size,
                visit_date,
            ),
        )
        for attraction in cluster:
            preferred_dates[attraction.id] = selected_date
        assigned_duration[selected_date] += cluster_duration
        assigned_energy[selected_date] += cluster_energy
        assigned_count[selected_date] += cluster_size

    return preferred_dates


def _cluster_attractions_by_od(
    attractions: tuple[Attraction, ...],
    cluster_count: int,
    provider: TravelTimeProvider,
) -> tuple[tuple[Attraction, ...], ...]:
    """Create deterministic average-linkage clusters from a directed OD snapshot."""

    if not attractions:
        return ()
    if not 1 <= cluster_count <= len(attractions):
        raise ValueError("cluster_count must be within 1..len(attractions)")

    max_cluster_size = (len(attractions) + cluster_count - 1) // cluster_count
    clusters: list[tuple[Attraction, ...]] = [
        (item,) for item in sorted(attractions, key=lambda item: item.id)
    ]
    while len(clusters) > cluster_count:
        candidates: list[
            tuple[Fraction, int, tuple[int, ...], int, int]
        ] = []
        for left_index, left in enumerate(clusters):
            for right_index in range(left_index + 1, len(clusters)):
                right = clusters[right_index]
                merged_size = len(left) + len(right)
                if merged_size > max_cluster_size:
                    continue
                merged_ids = tuple(sorted(item.id for item in (*left, *right)))
                candidates.append(
                    (
                        _average_cluster_od_cost(left, right, provider),
                        merged_size,
                        merged_ids,
                        left_index,
                        right_index,
                    )
                )
        if not candidates:
            raise RuntimeError("unable to form capacity-safe OD clusters")
        _, _, _, left_index, right_index = min(candidates)
        merged = tuple(
            sorted(
                (*clusters[left_index], *clusters[right_index]),
                key=lambda item: item.id,
            )
        )
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in {left_index, right_index}
        ]
        clusters.append(merged)
        clusters.sort(key=lambda cluster: tuple(item.id for item in cluster))
    size_balanced = _rebalance_od_cluster_sizes(tuple(clusters), provider)
    return _rebalance_od_cluster_durations(size_balanced, provider)


def _rebalance_od_cluster_sizes(
    clusters: tuple[tuple[Attraction, ...], ...],
    provider: TravelTimeProvider,
) -> tuple[tuple[Attraction, ...], ...]:
    """Keep OD clusters useful while ensuring day counts differ by at most one."""

    mutable = [list(cluster) for cluster in clusters]
    while max(map(len, mutable)) - min(map(len, mutable)) > 1:
        largest = max(map(len, mutable))
        smallest = min(map(len, mutable))
        candidates: list[
            tuple[Fraction, Fraction, int, tuple[int, ...], tuple[int, ...], int, int]
        ] = []
        for donor_index, donor in enumerate(mutable):
            if len(donor) != largest:
                continue
            for recipient_index, recipient in enumerate(mutable):
                if len(recipient) != smallest:
                    continue
                for attraction in donor:
                    donor_others = [item for item in donor if item.id != attraction.id]
                    lost_affinity = _average_attraction_cluster_cost(
                        attraction,
                        donor_others,
                        provider,
                    )
                    gained_affinity = _average_attraction_cluster_cost(
                        attraction,
                        recipient,
                        provider,
                    )
                    candidates.append(
                        (
                            gained_affinity - lost_affinity,
                            gained_affinity,
                            attraction.id,
                            tuple(item.id for item in donor),
                            tuple(item.id for item in recipient),
                            donor_index,
                            recipient_index,
                        )
                    )
        if not candidates:
            raise RuntimeError("unable to rebalance OD clusters")
        selected = min(candidates)
        attraction_id = selected[2]
        donor_index = selected[-2]
        recipient_index = selected[-1]
        attraction = next(
            item for item in mutable[donor_index] if item.id == attraction_id
        )
        mutable[donor_index].remove(attraction)
        mutable[recipient_index].append(attraction)
        mutable[donor_index].sort(key=lambda item: item.id)
        mutable[recipient_index].sort(key=lambda item: item.id)

    return tuple(
        tuple(cluster)
        for cluster in sorted(mutable, key=lambda items: tuple(item.id for item in items))
    )


def _average_attraction_cluster_cost(
    attraction: Attraction,
    cluster: list[Attraction],
    provider: TravelTimeProvider,
) -> Fraction:
    costs = [
        _symmetric_od_cost(attraction.id, other.id, provider)
        for other in cluster
    ]
    return Fraction(sum(costs), len(costs))


def _rebalance_od_cluster_durations(
    clusters: tuple[tuple[Attraction, ...], ...],
    provider: TravelTimeProvider,
) -> tuple[tuple[Attraction, ...], ...]:
    """Reduce extreme day-load gaps when the added OD cost stays small."""

    mutable = [list(cluster) for cluster in clusters]
    total_count = sum(map(len, mutable))
    minimum_size = total_count // len(mutable)
    maximum_size = (total_count + len(mutable) - 1) // len(mutable)
    while True:
        durations = [
            sum(item.suggested_duration for item in cluster)
            for cluster in mutable
        ]
        current_spread = max(durations) - min(durations)
        candidates: list[
            tuple[int, Fraction, int, tuple[int, ...], tuple[int, ...], int, int]
        ] = []
        for donor_index, donor in enumerate(mutable):
            if len(donor) <= minimum_size:
                continue
            for recipient_index, recipient in enumerate(mutable):
                if donor_index == recipient_index or len(recipient) >= maximum_size:
                    continue
                for attraction in donor:
                    proposed = durations.copy()
                    proposed[donor_index] -= attraction.suggested_duration
                    proposed[recipient_index] += attraction.suggested_duration
                    improvement = current_spread - (max(proposed) - min(proposed))
                    if improvement <= 0:
                        continue
                    donor_others = [item for item in donor if item.id != attraction.id]
                    od_penalty = _average_attraction_cluster_cost(
                        attraction,
                        recipient,
                        provider,
                    ) - _average_attraction_cluster_cost(
                        attraction,
                        donor_others,
                        provider,
                    )
                    if (
                        od_penalty
                        > DEFAULT_OD_DURATION_REBALANCE_MAX_SYMMETRIC_PENALTY_MIN
                    ):
                        continue
                    candidates.append(
                        (
                            -improvement,
                            od_penalty,
                            attraction.id,
                            tuple(item.id for item in donor),
                            tuple(item.id for item in recipient),
                            donor_index,
                            recipient_index,
                        )
                    )
        if not candidates:
            break
        selected = min(candidates)
        attraction_id = selected[2]
        donor_index = selected[-2]
        recipient_index = selected[-1]
        attraction = next(
            item for item in mutable[donor_index] if item.id == attraction_id
        )
        mutable[donor_index].remove(attraction)
        mutable[recipient_index].append(attraction)
        mutable[donor_index].sort(key=lambda item: item.id)
        mutable[recipient_index].sort(key=lambda item: item.id)

    return tuple(
        tuple(cluster)
        for cluster in sorted(mutable, key=lambda items: tuple(item.id for item in items))
    )


def _average_cluster_od_cost(
    left: tuple[Attraction, ...],
    right: tuple[Attraction, ...],
    provider: TravelTimeProvider,
) -> Fraction:
    costs = [
        _symmetric_od_cost(origin.id, destination.id, provider)
        for origin in left
        for destination in right
    ]
    return Fraction(sum(costs), len(costs))


def _symmetric_od_cost(
    origin_id: int,
    destination_id: int,
    provider: TravelTimeProvider,
) -> int:
    forward = provider.get_travel_time(origin_id, destination_id)
    backward = provider.get_travel_time(destination_id, origin_id)
    available = [
        item.travel_min
        for item in (forward, backward)
        if item is not None
    ]
    if len(available) == 2:
        return sum(available)
    if len(available) == 1:
        return max(available[0] * 4, 240)
    return 10_000


def _visit_period(raw: dict[str, object] | None) -> VisitPeriodPreference | None:
    if raw is None:
        return None
    return VisitPeriodPreference(
        frozenset({TimeBucket(_text(raw["preferred_bucket"]))}),
        frozenset(
            TimeBucket(_text(item)) for item in _list(raw["acceptable_buckets"])
        ),
        VisitPeriodPreferenceSource.USER,
        "generation_input",
    )


def _result_snapshot(request, published, itinerary, quality, degradation):
    external_by_solver_id = {
        item.attraction.id: item.external_id for item in published.attractions
    }
    days = []
    for day in itinerary.days:
        occurrences: dict[int, int] = {}
        nodes = []
        for visit in day.visits:
            window_resolution = resolve_effective_window(
                visit.attraction,
                day.visit_date,
            )
            effective_window = window_resolution.window
            timing_kind = (
                "fixed_event"
                if effective_window is not None
                and effective_window.close_min - effective_window.open_min <= 60
                else "flexible"
            )
            occurrences[visit.attraction.id] = occurrences.get(visit.attraction.id, 0) + 1
            node_key = (
                f"{request.generation_intent_id}|{day.visit_date.isoformat()}|"
                f"{visit.attraction.id}|{occurrences[visit.attraction.id]}"
            )
            nodes.append(
                {
                    "node_id": "node_" + hashlib.sha256(node_key.encode()).hexdigest()[:20],
                    "attraction_id": external_by_solver_id[visit.attraction.id],
                    "name": visit.attraction.name,
                    "arrival_min": visit.arrival_min,
                    "leave_min": visit.leave_min,
                    "planned_duration_min": visit.planned_duration_min,
                    "travel_from_previous_min": (
                        visit.travel_from_previous.travel_min
                        if visit.travel_from_previous is not None
                        else 0
                    ),
                    "buffered_travel_from_previous_min": (
                        visit.buffered_travel_from_previous_min
                    ),
                    "travel_basis": (
                        visit.travel_from_previous.basis.value
                        if visit.travel_from_previous is not None
                        else None
                    ),
                    "travel_distance_m": (
                        visit.travel_from_previous.distance_m
                        if visit.travel_from_previous is not None
                        else None
                    ),
                    "travel_fallback_reason": (
                        visit.travel_from_previous.fallback_reason
                        if visit.travel_from_previous is not None
                        else None
                    ),
                    "transport_mode": (
                        _transport_mode(visit.travel_from_previous)
                        if visit.travel_from_previous is not None
                        else None
                    ),
                    "timing_kind": timing_kind,
                    "duration_notice": visit.duration_notice,
                    "visit_period": _jsonable(visit.visit_period),
                }
            )
        segmented = next(
            (
                item
                for item in itinerary.segmented_days
                if item.routed_day.visit_date == day.visit_date
            ),
            None,
        )
        days.append(
            {
                "date": day.visit_date.isoformat(),
                "search_status": day.solve_metadata.status.value,
                "total_travel_min": day.total_travel_min,
                "weather": _jsonable(published.weather_by_date[day.visit_date]),
                "nodes": nodes,
                "lunch": _lunch_plan(day),
                "meal": _jsonable(segmented.meal_plan) if segmented is not None else None,
            }
        )
    accounting = quality.accounting
    return {
        "schema_version": "trip-result-v2",
        "provenance": {
            "solver_version": SOLVER_CONTRACT_VERSION,
            "constraint_version": CONSTRAINT_VERSION,
            "parameter_version": PARAMETER_VERSION,
            "data_snapshot_version": published.version,
            "input_snapshot_hash": request.input_snapshot_hash,
            "random_seed": request.random_seed,
            "od_basis": published.od_basis,
            "weather_basis": published.weather_basis,
        },
        "summary": {
            "day_count": len(itinerary.days),
            "scheduled_count": accounting.scheduled_count,
            "unplaced_count": accounting.unplaced_count,
            "data_rejected_count": accounting.data_rejected_count,
            "total_travel_min": sum(day.total_travel_min for day in itinerary.days),
        },
        "accounting": _jsonable(accounting),
        "days": days,
        "unplaced": [
            {
                "attraction_id": external_by_solver_id[item.attraction.id],
                "name": item.attraction.name,
                "reason_code": item.rejection_code.value,
            }
            for item in itinerary.unplaced
        ],
        "data_rejected": [
            {
                "attraction_id": external_by_solver_id[item.attraction.id],
                "name": item.attraction.name,
                "reason_code": item.code.value,
            }
            for item in itinerary.data_rejected
        ],
        "reassignments": [
            {
                "attraction_id": external_by_solver_id[item.attraction.id],
                "from_date": item.from_date.isoformat(),
                "to_date": item.to_date.isoformat(),
            }
            for item in itinerary.reassignments
        ],
        "degradations": [_jsonable(item) for item in degradation.notices],
        "quality_gate_passed": quality.gate_passed,
    }


def _transport_mode(travel: TravelTimeResult) -> str:
    if travel.travel_mode is not None:
        return travel.travel_mode.value
    if travel.travel_min <= 8:
        return "walking_estimate"
    if travel.travel_min <= 20:
        return "taxi_estimate"
    return "transit_or_taxi_estimate"


def _lunch_plan(day) -> dict[str, object] | None:
    visits = day.visits
    if not visits:
        return None

    intervals: list[tuple[str, int, int]] = [
        ("before_first_visit", day.bounds.start_min, visits[0].arrival_min)
    ]
    intervals.extend(
        (
            "between_visits",
            previous.leave_min,
            current.arrival_min - current.buffered_travel_from_previous_min,
        )
        for previous, current in zip(visits, visits[1:], strict=False)
    )
    intervals.append(
        ("after_last_visit", visits[-1].leave_min, day.bounds.end_min)
    )

    for duration_min, status in (
        (LUNCH_FULL_DURATION_MIN, "full"),
        (LUNCH_REDUCED_DURATION_MIN, "reduced"),
    ):
        for placement, interval_start, interval_end in intervals:
            start_min = max(interval_start, LUNCH_EARLIEST_MIN)
            end_limit = min(interval_end, LUNCH_LATEST_END_MIN)
            if end_limit - start_min >= duration_min:
                return {
                    "status": status,
                    "placement": placement,
                    "start_min": start_min,
                    "end_min": start_min + duration_min,
                    "duration_min": duration_min,
                    "notice": (
                        f"已预留 {duration_min} 分钟午餐"
                        if status == "full"
                        else f"午餐留白缩短为 {duration_min} 分钟"
                    ),
                }

    return {
        "status": "unscheduled",
        "placement": None,
        "start_min": None,
        "end_min": None,
        "duration_min": 0,
        "notice": "当日午餐时间紧张，请提前用餐或准备简餐",
    }


def _duration_ratio(mode: TravelMode) -> float:
    return 0.7 if mode is TravelMode.LEISURE else 0.6


def _minute_of_day(value: datetime) -> int:
    if value.tzinfo is None:
        raise ValueError("travel datetime must be timezone-aware")
    return value.hour * 60 + value.minute


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected object")
    return value


def _list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError("expected list")
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError("expected non-empty string")
    return value


def _jsonable(value: object) -> object:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(item) for item in value]
    return value


def _stable_hash(value: dict[str, object]) -> str:
    serialized = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
