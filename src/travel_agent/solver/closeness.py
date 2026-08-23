"""Explainable closeness between a solved itinerary and a reviewed baseline.

Traceability: H3, Gate 6, ADR-0006, ADR-0007.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from .models import ItineraryPlan
from .quality import SolverQualityReport


class BaselineProvenance(StrEnum):
    DOMAIN_EXPERT = "domain_expert"
    HUMAN_REVIEWED = "human_reviewed"
    PUBLIC_GUIDE_SYNTHESIS = "public_guide_synthesis"


class TimeBucket(StrEnum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"


@dataclass(frozen=True, slots=True)
class VisitExpectation:
    attraction_id: int
    preferred_day: date | None = None
    acceptable_days: frozenset[date] = frozenset()
    preferred_buckets: frozenset[TimeBucket] = frozenset()
    acceptable_buckets: frozenset[TimeBucket] = frozenset()
    fixed_day: bool = False
    fixed_bucket: bool = False

    def __post_init__(self) -> None:
        if self.fixed_day and self.preferred_day is None:
            raise ValueError("fixed_day requires preferred_day")
        if self.fixed_bucket and not self.preferred_buckets:
            raise ValueError("fixed_bucket requires preferred_buckets")


@dataclass(frozen=True, slots=True)
class SameDayExpectation:
    attraction_ids: frozenset[int]
    weight: float = 1.0
    fixed: bool = False

    def __post_init__(self) -> None:
        if len(self.attraction_ids) < 2:
            raise ValueError("same-day expectation requires at least two attractions")
        if self.weight <= 0:
            raise ValueError("same-day expectation weight must be positive")


@dataclass(frozen=True, slots=True)
class AdjacencyExpectation:
    first_id: int
    second_id: int
    directional: bool = False
    weight: float = 1.0
    fixed: bool = False

    def __post_init__(self) -> None:
        if self.first_id == self.second_id:
            raise ValueError("adjacency endpoints must differ")
        if self.weight <= 0:
            raise ValueError("adjacency expectation weight must be positive")


@dataclass(frozen=True, slots=True)
class ItineraryBaseline:
    baseline_id: str
    version: str
    provenance: BaselineProvenance
    source_refs: tuple[str, ...]
    visit_expectations: tuple[VisitExpectation, ...] = ()
    same_day_expectations: tuple[SameDayExpectation, ...] = ()
    adjacency_expectations: tuple[AdjacencyExpectation, ...] = ()

    def __post_init__(self) -> None:
        if not self.baseline_id or not self.version:
            raise ValueError("baseline id and version are required")
        if not self.source_refs:
            raise ValueError("baseline must retain at least one source reference")
        if not (
            self.visit_expectations
            or self.same_day_expectations
            or self.adjacency_expectations
        ):
            raise ValueError("baseline must contain at least one scored expectation")
        ids = [item.attraction_id for item in self.visit_expectations]
        if len(ids) != len(set(ids)):
            raise ValueError("visit expectations must contain unique attraction ids")


@dataclass(frozen=True, slots=True)
class ClosenessComponent:
    name: str
    score: float | None
    matched_weight: float
    total_weight: float

    def __post_init__(self) -> None:
        if self.matched_weight < 0 or self.total_weight < 0:
            raise ValueError("component weights must be non-negative")
        if self.score is None:
            if self.total_weight != 0:
                raise ValueError("unscored component must have zero total weight")
        elif not 0 <= self.score <= 1:
            raise ValueError("component score must be within 0..1")


@dataclass(frozen=True, slots=True)
class ItineraryClosenessReport:
    baseline_id: str
    baseline_version: str
    provenance: BaselineProvenance
    source_refs: tuple[str, ...]
    hard_gate_passed: bool
    fixed_item_count: int
    fixed_item_matched: int
    fixed_visit_score: float
    day_assignment: ClosenessComponent
    time_bucket: ClosenessComponent
    same_day: ClosenessComponent
    adjacency: ClosenessComponent
    overall_closeness: float
    threshold: float
    baseline_passed: bool

    def __post_init__(self) -> None:
        if not 0 <= self.fixed_visit_score <= 1:
            raise ValueError("fixed visit score must be within 0..1")
        if not 0 <= self.overall_closeness <= 1:
            raise ValueError("overall closeness must be within 0..1")
        if not 0 <= self.threshold <= 1:
            raise ValueError("closeness threshold must be within 0..1")
        expected = (
            self.hard_gate_passed
            and self.fixed_visit_score == 1
            and self.overall_closeness >= self.threshold
        )
        if self.baseline_passed != expected:
            raise ValueError("baseline result is inconsistent")


COMPONENT_WEIGHTS = {
    "day_assignment": 0.35,
    "time_bucket": 0.25,
    "same_day": 0.20,
    "adjacency": 0.20,
}


def evaluate_itinerary_closeness(
    itinerary: ItineraryPlan,
    quality: SolverQualityReport,
    baseline: ItineraryBaseline,
    *,
    threshold: float = 0.75,
) -> ItineraryClosenessReport:
    """Score reviewed soft expectations after the hard quality gate."""

    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be within 0..1")
    visits = {
        visit.attraction.id: (day.visit_date, _time_bucket(visit.arrival_min))
        for day in itinerary.days
        for visit in day.visits
    }
    day_component = _day_assignment_component(baseline, visits)
    bucket_component = _time_bucket_component(baseline, visits)
    same_day_component = _same_day_component(baseline, visits)
    adjacency_component = _adjacency_component(baseline, itinerary)
    fixed_matched, fixed_total = _fixed_matches(baseline, visits, itinerary)
    fixed_score = fixed_matched / fixed_total if fixed_total else 1.0
    overall = _overall(
        day_component,
        bucket_component,
        same_day_component,
        adjacency_component,
    )
    hard_gate = quality.gate_passed
    return ItineraryClosenessReport(
        baseline.baseline_id,
        baseline.version,
        baseline.provenance,
        baseline.source_refs,
        hard_gate,
        fixed_total,
        fixed_matched,
        fixed_score,
        day_component,
        bucket_component,
        same_day_component,
        adjacency_component,
        overall,
        threshold,
        hard_gate and fixed_score == 1 and overall >= threshold,
    )


def _day_assignment_component(
    baseline: ItineraryBaseline,
    visits: dict[int, tuple[date, TimeBucket]],
) -> ClosenessComponent:
    scores: list[float] = []
    for expectation in baseline.visit_expectations:
        actual = visits.get(expectation.attraction_id)
        if expectation.preferred_day is None and not expectation.acceptable_days:
            continue
        if actual is None:
            scores.append(0)
        elif expectation.preferred_day is not None and actual[0] == expectation.preferred_day:
            scores.append(1)
        elif actual[0] in expectation.acceptable_days:
            scores.append(0.7 if expectation.preferred_day is not None else 1.0)
        else:
            scores.append(0)
    return _component("day_assignment", scores)


def _time_bucket_component(
    baseline: ItineraryBaseline,
    visits: dict[int, tuple[date, TimeBucket]],
) -> ClosenessComponent:
    scores: list[float] = []
    for expectation in baseline.visit_expectations:
        if not expectation.preferred_buckets and not expectation.acceptable_buckets:
            continue
        actual = visits.get(expectation.attraction_id)
        if actual is None:
            scores.append(0)
        elif actual[1] in expectation.preferred_buckets:
            scores.append(1)
        elif actual[1] in expectation.acceptable_buckets:
            scores.append(0.7 if expectation.preferred_buckets else 1.0)
        else:
            scores.append(0)
    return _component("time_bucket", scores)


def _same_day_component(
    baseline: ItineraryBaseline,
    visits: dict[int, tuple[date, TimeBucket]],
) -> ClosenessComponent:
    matched = 0.0
    total = 0.0
    for expectation in baseline.same_day_expectations:
        total += expectation.weight
        dates = {
            visits[item][0]
            for item in expectation.attraction_ids
            if item in visits
        }
        if len(dates) == 1 and all(item in visits for item in expectation.attraction_ids):
            matched += expectation.weight
    return _weighted_component("same_day", matched, total)


def _adjacency_component(
    baseline: ItineraryBaseline,
    itinerary: ItineraryPlan,
) -> ClosenessComponent:
    directed: set[tuple[int, int]] = set()
    for day in itinerary.days:
        ids = [visit.attraction.id for visit in day.visits]
        directed.update(zip(ids, ids[1:], strict=False))
    matched = 0.0
    total = 0.0
    for expectation in baseline.adjacency_expectations:
        total += expectation.weight
        forward = (expectation.first_id, expectation.second_id) in directed
        reverse = (expectation.second_id, expectation.first_id) in directed
        if forward or (reverse and not expectation.directional):
            matched += expectation.weight
    return _weighted_component("adjacency", matched, total)


def _fixed_matches(
    baseline: ItineraryBaseline,
    visits: dict[int, tuple[date, TimeBucket]],
    itinerary: ItineraryPlan,
) -> tuple[int, int]:
    matched = 0
    total = 0
    for expectation in baseline.visit_expectations:
        actual = visits.get(expectation.attraction_id)
        if expectation.fixed_day:
            total += 1
            matched += int(
                actual is not None and actual[0] == expectation.preferred_day
            )
        if expectation.fixed_bucket:
            total += 1
            matched += int(
                actual is not None and actual[1] in expectation.preferred_buckets
            )
    for expectation in baseline.same_day_expectations:
        if not expectation.fixed:
            continue
        total += 1
        dates = {
            visits[item][0]
            for item in expectation.attraction_ids
            if item in visits
        }
        matched += int(
            len(dates) == 1
            and all(item in visits for item in expectation.attraction_ids)
        )
    directed = {
        pair
        for day in itinerary.days
        for pair in zip(
            [visit.attraction.id for visit in day.visits],
            [visit.attraction.id for visit in day.visits][1:],
            strict=False,
        )
    }
    for expectation in baseline.adjacency_expectations:
        if not expectation.fixed:
            continue
        total += 1
        forward = (expectation.first_id, expectation.second_id) in directed
        reverse = (expectation.second_id, expectation.first_id) in directed
        matched += int(forward or (reverse and not expectation.directional))
    return matched, total


def _component(name: str, scores: list[float]) -> ClosenessComponent:
    if not scores:
        return ClosenessComponent(name, None, 0, 0)
    return ClosenessComponent(name, sum(scores) / len(scores), sum(scores), len(scores))


def _weighted_component(name: str, matched: float, total: float) -> ClosenessComponent:
    if total == 0:
        return ClosenessComponent(name, None, 0, 0)
    return ClosenessComponent(name, matched / total, matched, total)


def _overall(*components: ClosenessComponent) -> float:
    available = [item for item in components if item.score is not None]
    if not available:
        return 1.0
    total_weight = sum(COMPONENT_WEIGHTS[item.name] for item in available)
    return sum(
        COMPONENT_WEIGHTS[item.name] * item.score
        for item in available
        if item.score is not None
    ) / total_weight


def _time_bucket(arrival_min: int) -> TimeBucket:
    if arrival_min < 12 * 60:
        return TimeBucket.MORNING
    if arrival_min < 17 * 60:
        return TimeBucket.AFTERNOON
    return TimeBucket.EVENING
