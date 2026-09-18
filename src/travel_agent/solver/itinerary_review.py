"""Deterministic, explainable experience review for a routed itinerary.

Hard feasibility remains owned by ``quality.py``. This module only ranks
already-routed candidates and cannot turn a hard failure into a success.

Traceability: H2, H3, H7, S1, S2, ADR-0028.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum

from .models import (
    Attraction,
    ItineraryPlan,
    MealPlan,
    MealStatus,
    ODBasis,
    RoutedDay,
    RouteVisit,
    TravelMode,
    VisitPeriodOutcome,
)
from .quality_policy import (
    QUALITY_CONTINUOUS_ACTIVITY_BALANCED_MIN,
    QUALITY_CONTINUOUS_ACTIVITY_RELAXED_MIN,
    QUALITY_CONTINUOUS_ACTIVITY_TIGHT_MIN,
    QUALITY_DINNER_MIN_USABLE_MIN,
    QUALITY_DINNER_TARGET_MIN,
    QUALITY_FIXED_CONNECTION_SEVERE_MIN,
    QUALITY_HALF_DAY_IDLE_MIN,
    QUALITY_LUNCH_MIN_USABLE_MIN,
    QUALITY_LUNCH_TARGET_MIN,
    QUALITY_NEIGHBOUR_DISTANCE_M,
    QUALITY_NEIGHBOUR_SEVERE_EDGE_WEIGHT,
    QUALITY_NEIGHBOUR_SYMMETRIC_MIN,
    QUALITY_SCORE_TARGET_BPS,
    QUALITY_VISIT_SEVERE_RATIO_PER_MILLE,
)
from .transport import TravelTimeProvider

SCORING_POLICY_VERSION = "expert-itinerary-review-v1"
WEIGHT_PROFILE_VERSION = "expert-default-2026-09-18"


class ReviewDimension(StrEnum):
    GEOGRAPHY = "G"
    VISIT_VALUE = "V"
    PACE = "P"
    ROBUSTNESS = "R"
    MEALS = "M"
    FATIGUE = "F"
    USER_INTENT = "U"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    SEVERE = "severe"


class DiagnosticAttribution(StrEnum):
    DATA = "data"
    CONSTRAINT = "constraint"
    PREFERENCE = "preference"
    SEARCH = "search"


@dataclass(frozen=True, slots=True)
class ReviewDiagnostic:
    code: str
    rule_id: str
    dimension: ReviewDimension
    severity: DiagnosticSeverity
    attribution: DiagnosticAttribution
    loss_per_mille: int
    attraction_ids: tuple[int, ...] = ()
    visit_dates: tuple[str, ...] = ()
    measured_value: int | None = None
    threshold_value: int | None = None
    unit: str | None = None
    suggested_actions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class DimensionReview:
    dimension: ReviewDimension
    weight: int
    applicable: bool
    loss_per_mille: int
    score_basis_points: int


@dataclass(frozen=True, slots=True)
class EvidenceReview:
    coverage_per_mille: int
    verified_attraction_count: int
    attraction_count: int
    evidenced_connection_count: int
    connection_count: int


@dataclass(frozen=True, slots=True)
class ItineraryExperienceReview:
    scoring_policy_version: str
    weight_profile_version: str
    score_basis_points: int
    dimensions: tuple[DimensionReview, ...]
    diagnostics: tuple[ReviewDiagnostic, ...]
    severe_issue_count: int
    scheduled_count: int
    input_count: int
    evidence: EvidenceReview
    quality_target_met: bool
    total_travel_min: int
    user_edit_distance: int
    stable_fingerprint: str

    @property
    def weighted_loss(self) -> int:
        return 10_000 - self.score_basis_points

    @property
    def rank_key(self) -> tuple[int, int, int, int, int, str]:
        """Lower is better; coverage and severe deficits cannot be averaged away."""

        return (
            self.input_count - self.scheduled_count,
            self.severe_issue_count,
            self.weighted_loss,
            self.total_travel_min,
            self.user_edit_distance,
            self.stable_fingerprint,
        )

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["score"] = self.score_basis_points / 100
        return payload


@dataclass(frozen=True, slots=True)
class ItineraryWeightProfile:
    version: str
    weights: tuple[tuple[ReviewDimension, int], ...]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("weight profile version is required")
        dimensions = tuple(dimension for dimension, _ in self.weights)
        if len(set(dimensions)) != len(dimensions) or set(dimensions) != set(ReviewDimension):
            raise ValueError("weight profile must define every dimension exactly once")
        if (
            any(weight <= 0 for _, weight in self.weights)
            or sum(weight for _, weight in self.weights) != 100
        ):
            raise ValueError("weight profile weights must be positive and sum to 100")

    def weight_for(self, dimension: ReviewDimension) -> int:
        return dict(self.weights)[dimension]


DEFAULT_EXPERT_WEIGHT_PROFILE = ItineraryWeightProfile(
    WEIGHT_PROFILE_VERSION,
    (
        (ReviewDimension.GEOGRAPHY, 20),
        (ReviewDimension.VISIT_VALUE, 20),
        (ReviewDimension.PACE, 15),
        (ReviewDimension.ROBUSTNESS, 15),
        (ReviewDimension.MEALS, 12),
        (ReviewDimension.FATIGUE, 8),
        (ReviewDimension.USER_INTENT, 10),
    ),
)


@dataclass(frozen=True, slots=True)
class ReviewContext:
    attractions: tuple[Attraction, ...]
    baseline_day_by_id: Mapping[int, int]
    travel_mode: TravelMode
    weight_profile: ItineraryWeightProfile


def build_review_context(
    attractions: Iterable[Attraction],
    itinerary: ItineraryPlan,
    *,
    travel_mode: TravelMode = TravelMode.NORMAL,
    weight_profile: ItineraryWeightProfile = DEFAULT_EXPERT_WEIGHT_PROFILE,
) -> ReviewContext:
    selected = tuple(attractions)
    return ReviewContext(
        selected,
        {
            visit.attraction.id: day_index
            for day_index, day in enumerate(itinerary.days)
            for visit in day.visits
        },
        travel_mode,
        weight_profile,
    )


def evaluate_itinerary_experience(
    itinerary: ItineraryPlan,
    context: ReviewContext,
    provider: TravelTimeProvider,
) -> ItineraryExperienceReview:
    meals = {
        item.routed_day.visit_date.isoformat(): item.meal_plan for item in itinerary.segmented_days
    }
    return evaluate_routed_experience(
        itinerary.days,
        context,
        provider,
        meal_by_date=meals,
    )


def evaluate_routed_experience(
    days: Iterable[RoutedDay],
    context: ReviewContext,
    provider: TravelTimeProvider,
    *,
    meal_by_date: Mapping[str, MealPlan] | None = None,
) -> ItineraryExperienceReview:
    routed_days = tuple(sorted(days, key=lambda item: item.visit_date))
    meals = meal_by_date or {}
    diagnostics: list[ReviewDiagnostic] = []
    scheduled = tuple(visit for day in routed_days for visit in day.visits)
    day_by_id = {
        visit.attraction.id: day_index
        for day_index, day in enumerate(routed_days)
        for visit in day.visits
    }

    geography_loss = _geography_loss(
        routed_days,
        context.attractions,
        day_by_id,
        provider,
        diagnostics,
    )
    visit_loss = _visit_value_loss(scheduled, diagnostics)
    pace_loss = _pace_loss(routed_days, diagnostics)
    robustness_loss = _robustness_loss(routed_days, meals, context.travel_mode, diagnostics)
    meal_loss = _meal_loss(routed_days, meals, diagnostics)
    fatigue_loss = _fatigue_loss(routed_days, context.travel_mode, diagnostics)
    intent_loss, intent_applicable = _intent_loss(routed_days, diagnostics)

    losses: dict[ReviewDimension, tuple[int, bool]] = {
        ReviewDimension.GEOGRAPHY: (geography_loss, len(context.attractions) > 1),
        ReviewDimension.VISIT_VALUE: (visit_loss, bool(context.attractions)),
        ReviewDimension.PACE: (pace_loss, bool(routed_days)),
        ReviewDimension.ROBUSTNESS: (robustness_loss, len(scheduled) > 1),
        ReviewDimension.MEALS: (meal_loss, bool(routed_days)),
        ReviewDimension.FATIGUE: (fatigue_loss, bool(scheduled)),
        ReviewDimension.USER_INTENT: (intent_loss, intent_applicable),
    }
    weight_profile = context.weight_profile
    applicable_weight = sum(
        weight_profile.weight_for(dimension)
        for dimension, (_, applicable) in losses.items()
        if applicable
    )
    weighted_loss = sum(
        weight_profile.weight_for(dimension) * loss
        for dimension, (loss, applicable) in losses.items()
        if applicable
    )
    normalized_loss = weighted_loss // max(1, applicable_weight)
    dimensions = tuple(
        DimensionReview(
            dimension,
            weight_profile.weight_for(dimension),
            applicable,
            loss if applicable else 0,
            10_000 - loss * 10 if applicable else 10_000,
        )
        for dimension, (loss, applicable) in losses.items()
    )
    evidence = _evidence(context.attractions, routed_days)
    severe_count = len(
        {item.rule_id for item in diagnostics if item.severity is DiagnosticSeverity.SEVERE}
    )
    score_basis_points = max(0, 10_000 - normalized_loss * 10)
    fingerprint = "|".join(
        f"{day.visit_date.isoformat()}:"
        + ",".join(
            f"{visit.attraction.id}@{visit.arrival_min}-{visit.leave_min}" for visit in day.visits
        )
        for day in routed_days
    )
    edit_distance = sum(
        context.baseline_day_by_id.get(attraction_id, day_index) != day_index
        for attraction_id, day_index in day_by_id.items()
    )
    return ItineraryExperienceReview(
        SCORING_POLICY_VERSION,
        weight_profile.version,
        score_basis_points,
        dimensions,
        tuple(sorted(diagnostics, key=_diagnostic_key)),
        severe_count,
        len(scheduled),
        len(context.attractions),
        evidence,
        (
            len(scheduled) == len(context.attractions)
            and severe_count == 0
            and score_basis_points >= QUALITY_SCORE_TARGET_BPS
            and evidence.coverage_per_mille == 1000
        ),
        sum(day.total_travel_min for day in routed_days),
        edit_distance,
        fingerprint,
    )


def _geography_loss(
    days: tuple[RoutedDay, ...],
    attractions: tuple[Attraction, ...],
    day_by_id: Mapping[int, int],
    provider: TravelTimeProvider,
    diagnostics: list[ReviewDiagnostic],
) -> int:
    edges = _neighbour_edges(attractions, provider)
    edge_weight = sum(weight for _, _, weight in edges)
    split_weight = 0
    non_adjacent_weight = 0
    positions = {
        visit.attraction.id: (day_index, visit_index)
        for day_index, day in enumerate(days)
        for visit_index, visit in enumerate(day.visits)
    }
    for left, right, weight in edges:
        if left not in day_by_id or right not in day_by_id or day_by_id[left] != day_by_id[right]:
            split_weight += weight
            diagnostics.append(
                ReviewDiagnostic(
                    "NEIGHBOUR_SPLIT",
                    f"G1:{left}:{right}",
                    ReviewDimension.GEOGRAPHY,
                    (
                        DiagnosticSeverity.SEVERE
                        if weight >= QUALITY_NEIGHBOUR_SEVERE_EDGE_WEIGHT
                        else DiagnosticSeverity.WARNING
                    ),
                    DiagnosticAttribution.SEARCH,
                    0,
                    (left, right),
                    suggested_actions=("move_neighbour_group", "swap_across_days"),
                )
            )
        elif abs(positions[left][1] - positions[right][1]) > 1:
            non_adjacent_weight += weight
            diagnostics.append(
                ReviewDiagnostic(
                    "AVOIDABLE_BACKTRACK",
                    f"G2:{left}:{right}",
                    ReviewDimension.GEOGRAPHY,
                    DiagnosticSeverity.WARNING,
                    DiagnosticAttribution.SEARCH,
                    0,
                    (left, right),
                    suggested_actions=("reorder_within_day",),
                )
            )
    split_loss = split_weight * 1000 // max(1, edge_weight)
    backtrack_loss = non_adjacent_weight * 1000 // max(1, edge_weight)
    total_visit = sum(visit.planned_duration_min for day in days for visit in day.visits)
    total_travel = sum(day.total_travel_min for day in days)
    travel_loss = min(1000, total_travel * 1000 // max(1, total_visit + total_travel))
    return min(1000, (split_loss * 50 + backtrack_loss * 25 + travel_loss * 25) // 100)


def _neighbour_edges(
    attractions: tuple[Attraction, ...], provider: TravelTimeProvider
) -> tuple[tuple[int, int, int], ...]:
    nearest: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for left in attractions:
        for right in attractions:
            if left.id >= right.id:
                continue
            forward = provider.get_travel_time(left.id, right.id)
            backward = provider.get_travel_time(right.id, left.id)
            if forward is None or backward is None:
                continue
            distances = tuple(
                item.distance_m for item in (forward, backward) if item.distance_m is not None
            )
            symmetric = forward.travel_min + backward.travel_min
            qualifies = symmetric <= QUALITY_NEIGHBOUR_SYMMETRIC_MIN or (
                bool(distances)
                and min(distances) <= QUALITY_NEIGHBOUR_DISTANCE_M
                and not left.is_indoor
                and not right.is_indoor
            )
            if qualifies:
                nearest[left.id].append((symmetric, right.id))
                nearest[right.id].append((symmetric, left.id))
    top = {node: {other for _, other in sorted(values)[:2]} for node, values in nearest.items()}
    edges = []
    for left_id, neighbours in top.items():
        for right_id in neighbours:
            if left_id < right_id and left_id in top.get(right_id, set()):
                forward = provider.get_travel_time(left_id, right_id)
                backward = provider.get_travel_time(right_id, left_id)
                assert forward is not None and backward is not None
                symmetric = forward.travel_min + backward.travel_min
                edges.append((left_id, right_id, max(1, 1000 - min(999, symmetric * 20))))
    return tuple(sorted(edges))


def _visit_value_loss(visits: tuple[RouteVisit, ...], diagnostics: list[ReviewDiagnostic]) -> int:
    if not visits:
        return 1000
    losses = []
    for visit in visits:
        if visit.attraction.fixed_sessions:
            continue
        suggested = visit.attraction.suggested_duration
        loss = max(0, suggested - visit.planned_duration_min) * 1000 // suggested
        losses.append(loss)
        ratio = visit.planned_duration_min * 1000 // suggested
        if loss:
            diagnostics.append(
                ReviewDiagnostic(
                    "VISIT_SHORTFALL",
                    f"V1:{visit.attraction.id}",
                    ReviewDimension.VISIT_VALUE,
                    (
                        DiagnosticSeverity.SEVERE
                        if ratio < QUALITY_VISIT_SEVERE_RATIO_PER_MILLE
                        else DiagnosticSeverity.WARNING
                    ),
                    DiagnosticAttribution.SEARCH,
                    loss,
                    (visit.attraction.id,),
                    measured_value=ratio,
                    threshold_value=1000,
                    unit="ratio_per_mille",
                    suggested_actions=("extend_visit", "reduce_avoidable_travel"),
                )
            )
    return sum(losses) // max(1, len(losses))


def _pace_loss(days: tuple[RoutedDay, ...], diagnostics: list[ReviewDiagnostic]) -> int:
    if not days:
        return 1000
    rates = []
    counts = [len(day.visits) for day in days]
    for day in days:
        used = (
            sum(visit.planned_duration_min for visit in day.visits) + day.total_buffered_travel_min
        )
        rates.append(used * 1000 // max(1, day.bounds.end_min - day.bounds.start_min))
        gaps = _non_transit_gaps(day)
        for start, end in gaps:
            if end - start > QUALITY_HALF_DAY_IDLE_MIN and not _is_meal_gap(start, end):
                diagnostics.append(
                    ReviewDiagnostic(
                        "HALF_DAY_FRAGMENTED",
                        f"P2:{day.visit_date.isoformat()}:{start}",
                        ReviewDimension.PACE,
                        DiagnosticSeverity.WARNING,
                        DiagnosticAttribution.SEARCH,
                        min(1000, (end - start) * 1000 // 180),
                        visit_dates=(day.visit_date.isoformat(),),
                        measured_value=end - start,
                        threshold_value=QUALITY_HALF_DAY_IDLE_MIN,
                        unit="minutes",
                        suggested_actions=("move_visit_into_idle_period", "swap_across_days"),
                    )
                )
    imbalance = max(rates) - min(rates)
    if counts and min(counts) <= 1 and max(counts) >= min(counts) + 2:
        sparse_index = counts.index(min(counts))
        diagnostics.append(
            ReviewDiagnostic(
                "LOAD_IMBALANCE",
                f"P1:{days[sparse_index].visit_date.isoformat()}",
                ReviewDimension.PACE,
                DiagnosticSeverity.SEVERE,
                DiagnosticAttribution.SEARCH,
                min(1000, imbalance),
                visit_dates=(days[sparse_index].visit_date.isoformat(),),
                measured_value=imbalance,
                threshold_value=200,
                unit="load_per_mille",
                suggested_actions=("move_neighbour_group", "swap_across_days"),
            )
        )
    gap_loss = max(
        (item.loss_per_mille for item in diagnostics if item.dimension is ReviewDimension.PACE),
        default=0,
    )
    return min(1000, max(imbalance, gap_loss))


def _robustness_loss(
    days: tuple[RoutedDay, ...],
    meals: Mapping[str, MealPlan],
    travel_mode: TravelMode,
    diagnostics: list[ReviewDiagnostic],
) -> int:
    target = {TravelMode.SPEED: 10, TravelMode.NORMAL: 15, TravelMode.LEISURE: 20}[travel_mode]
    losses = []
    for day in days:
        meal = meals.get(day.visit_date.isoformat())
        for previous, current in zip(day.visits, day.visits[1:], strict=False):
            if not current.attraction.fixed_sessions:
                continue
            slack = (
                current.arrival_min - previous.leave_min - current.buffered_travel_from_previous_min
            )
            if (
                meal is not None
                and meal.start_min is not None
                and previous.leave_min <= meal.start_min < current.arrival_min
            ):
                slack -= meal.duration_min
            loss = max(0, target - slack) * 1000 // target
            losses.append(min(1000, loss))
            if loss:
                diagnostics.append(
                    ReviewDiagnostic(
                        "TIGHT_FIXED_CONNECTION",
                        f"R1:{day.visit_date.isoformat()}:{previous.attraction.id}:{current.attraction.id}",
                        ReviewDimension.ROBUSTNESS,
                        (
                            DiagnosticSeverity.SEVERE
                            if slack < QUALITY_FIXED_CONNECTION_SEVERE_MIN
                            else DiagnosticSeverity.WARNING
                        ),
                        DiagnosticAttribution.SEARCH,
                        min(1000, loss),
                        (previous.attraction.id, current.attraction.id),
                        (day.visit_date.isoformat(),),
                        slack,
                        target,
                        "minutes",
                        ("change_fixed_session", "move_preceding_group", "swap_across_days"),
                    )
                )
    return sum(losses) // max(1, len(losses)) if losses else 0


def _meal_loss(
    days: tuple[RoutedDay, ...],
    meals: Mapping[str, MealPlan],
    diagnostics: list[ReviewDiagnostic],
) -> int:
    losses = []
    for day in days:
        gaps = _non_transit_gaps(day)
        if day.bounds.start_min <= 13 * 60 and day.bounds.end_min >= 12 * 60 + 30:
            lunch = max(
                (_overlap(start, end, 11 * 60 + 30, 14 * 60) for start, end in gaps),
                default=0,
            )
            loss = max(0, QUALITY_LUNCH_TARGET_MIN - lunch) * 1000 // QUALITY_LUNCH_TARGET_MIN
            losses.append(loss)
            if loss:
                diagnostics.append(
                    ReviewDiagnostic(
                        "MEAL_GAP",
                        f"M1:lunch:{day.visit_date.isoformat()}",
                        ReviewDimension.MEALS,
                        (
                            DiagnosticSeverity.SEVERE
                            if lunch < QUALITY_LUNCH_MIN_USABLE_MIN
                            else DiagnosticSeverity.WARNING
                        ),
                        DiagnosticAttribution.SEARCH,
                        loss,
                        visit_dates=(day.visit_date.isoformat(),),
                        measured_value=lunch,
                        threshold_value=QUALITY_LUNCH_TARGET_MIN,
                        unit="minutes",
                        suggested_actions=("place_meal_block", "shift_or_swap_visits"),
                    )
                )
        if day.bounds.start_min <= 21 * 60 + 15 and day.bounds.end_min >= 17 * 60 + 15:
            meal = meals.get(day.visit_date.isoformat())
            dinner = (
                meal.duration_min
                if meal is not None and meal.status is not MealStatus.UNSCHEDULED
                else 0
            )
            loss = max(0, QUALITY_DINNER_TARGET_MIN - dinner) * 1000 // QUALITY_DINNER_TARGET_MIN
            losses.append(loss)
            if loss:
                diagnostics.append(
                    ReviewDiagnostic(
                        "MEAL_GAP",
                        f"M2:dinner:{day.visit_date.isoformat()}",
                        ReviewDimension.MEALS,
                        (
                            DiagnosticSeverity.SEVERE
                            if dinner < QUALITY_DINNER_MIN_USABLE_MIN
                            else DiagnosticSeverity.WARNING
                        ),
                        DiagnosticAttribution.SEARCH,
                        loss,
                        visit_dates=(day.visit_date.isoformat(),),
                        measured_value=dinner,
                        threshold_value=QUALITY_DINNER_TARGET_MIN,
                        unit="minutes",
                        suggested_actions=("place_meal_block", "split_evening_visits"),
                    )
                )
    return sum(losses) // max(1, len(losses)) if losses else 0


def _fatigue_loss(
    days: tuple[RoutedDay, ...],
    travel_mode: TravelMode,
    diagnostics: list[ReviewDiagnostic],
) -> int:
    limit = {
        TravelMode.SPEED: QUALITY_CONTINUOUS_ACTIVITY_TIGHT_MIN,
        TravelMode.NORMAL: QUALITY_CONTINUOUS_ACTIVITY_BALANCED_MIN,
        TravelMode.LEISURE: QUALITY_CONTINUOUS_ACTIVITY_RELAXED_MIN,
    }[travel_mode]
    energy = [sum(visit.attraction.energy_level for visit in day.visits) for day in days]
    balance_loss = (max(energy) - min(energy)) * 200 if energy else 0
    continuous_losses = []
    for day in days:
        block_start = day.visits[0].arrival_min if day.visits else 0
        previous_leave = block_start
        for visit in day.visits:
            if visit.arrival_min - visit.buffered_travel_from_previous_min - previous_leave >= 30:
                block_start = visit.arrival_min
            active = visit.leave_min - block_start
            if active > limit:
                continuous_losses.append(min(1000, (active - limit) * 1000 // 60))
            previous_leave = visit.leave_min
    loss = min(1000, max(balance_loss, max(continuous_losses, default=0)))
    if loss:
        diagnostics.append(
            ReviewDiagnostic(
                "FATIGUE",
                "F1:continuous-or-balance",
                ReviewDimension.FATIGUE,
                DiagnosticSeverity.WARNING,
                DiagnosticAttribution.SEARCH,
                loss,
                measured_value=loss,
                threshold_value=0,
                unit="loss_per_mille",
                suggested_actions=("rebalance_high_energy_visits", "add_real_rest_gap"),
            )
        )
    return loss


def _intent_loss(
    days: tuple[RoutedDay, ...], diagnostics: list[ReviewDiagnostic]
) -> tuple[int, bool]:
    evaluations = [
        visit.visit_period for day in days for visit in day.visits if visit.visit_period is not None
    ]
    if not evaluations:
        return 0, False
    losses = []
    for evaluation in evaluations:
        assert evaluation is not None
        loss = {
            VisitPeriodOutcome.PREFERRED: 0,
            VisitPeriodOutcome.ACCEPTABLE: 350,
            VisitPeriodOutcome.FALLBACK: 1000,
        }[evaluation.outcome]
        losses.append(loss)
        if loss:
            diagnostics.append(
                ReviewDiagnostic(
                    "USER_PERIOD_MISMATCH",
                    f"U1:{evaluation.preference.source_ref}:{evaluation.actual_bucket.value}",
                    ReviewDimension.USER_INTENT,
                    DiagnosticSeverity.WARNING,
                    DiagnosticAttribution.PREFERENCE,
                    loss,
                    measured_value=evaluation.deviation_min,
                    threshold_value=0,
                    unit="minutes",
                    suggested_actions=("reorder_within_day", "move_visit_to_preferred_period"),
                )
            )
    return sum(losses) // len(losses), True


def _evidence(attractions: tuple[Attraction, ...], days: tuple[RoutedDay, ...]) -> EvidenceReview:
    connections = [visit.travel_from_previous for day in days for visit in day.visits[1:]]
    evidenced = sum(item is not None and item.basis is ODBasis.GAODE for item in connections)
    verified = sum(item.data_verified for item in attractions)
    denominator = len(attractions) + len(connections)
    numerator = verified + evidenced
    return EvidenceReview(
        numerator * 1000 // max(1, denominator),
        verified,
        len(attractions),
        evidenced,
        len(connections),
    )


def _non_transit_gaps(day: RoutedDay) -> tuple[tuple[int, int], ...]:
    if not day.visits:
        return ((day.bounds.start_min, day.bounds.end_min),)
    gaps = [(day.bounds.start_min, day.visits[0].arrival_min)]
    gaps.extend(
        (
            previous.leave_min,
            current.arrival_min - current.buffered_travel_from_previous_min,
        )
        for previous, current in zip(day.visits, day.visits[1:], strict=False)
    )
    gaps.append((day.visits[-1].leave_min, day.bounds.end_min))
    return tuple((start, end) for start, end in gaps if end > start)


def _is_meal_gap(start: int, end: int) -> bool:
    return (
        _overlap(start, end, 11 * 60 + 30, 14 * 60) >= QUALITY_LUNCH_MIN_USABLE_MIN
        or _overlap(start, end, 16 * 60 + 30, 22 * 60) >= QUALITY_DINNER_MIN_USABLE_MIN
    )


def _overlap(start: int, end: int, window_start: int, window_end: int) -> int:
    return max(0, min(end, window_end) - max(start, window_start))


def _diagnostic_key(item: ReviewDiagnostic) -> tuple[str, str, tuple[int, ...], tuple[str, ...]]:
    return item.dimension.value, item.rule_id, item.attraction_ids, item.visit_dates
