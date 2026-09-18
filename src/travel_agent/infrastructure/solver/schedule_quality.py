"""Deterministic whole-trip soft improvement after hard recovery (H3, ADR-0027).

Only used for the gateway's derived default dates, never user-locked dates.
Moves and swaps are rerouted and independently validated before acceptance.
"""

from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from itertools import combinations
from time import perf_counter

from travel_agent.solver import (
    ItineraryPlan,
    Step1Plan,
    TravelTimeProvider,
)
from travel_agent.solver.day_assignment import rebuild_day_plan
from travel_agent.solver.itinerary import _precheck_target
from travel_agent.solver.itinerary_review import (
    ItineraryExperienceReview,
    build_review_context,
    evaluate_routed_experience,
)
from travel_agent.solver.models import DailyWeather, DayAllocation, DayPlan, SegmentedDay
from travel_agent.solver.quality_policy import (
    QUALITY_CANDIDATES_PER_ROUND,
    QUALITY_FIXED_CONNECTION_SEVERE_MIN,
    QUALITY_MAX_PASSES,
    QUALITY_NEIGHBOUR_DISTANCE_M,
    QUALITY_NEIGHBOUR_SYMMETRIC_MIN,
    QUALITY_ROUTE_BUDGET,
    QUALITY_WALL_TIME_LIMIT_SECONDS,
)
from travel_agent.solver.segments import route_segmented_day


class OptimizationStopReason(StrEnum):
    QUALITY_TARGET_MET = "quality_target_met"
    NO_NEW_CANDIDATE = "no_new_candidate"
    NO_IMPROVEMENT = "no_improvement"
    ROUTE_BUDGET = "route_budget"
    ROUND_BUDGET = "round_budget"
    WALL_TIME_LIMIT = "wall_time_limit"
    DATA_UNAVAILABLE = "data_unavailable"
    NO_FEASIBLE_SEED = "no_feasible_seed"


@dataclass(frozen=True, slots=True)
class ScheduleOptimizationResult:
    plan: Step1Plan
    initial_review: ItineraryExperienceReview | None
    searched_review: ItineraryExperienceReview | None
    stop_reason: OptimizationStopReason
    rounds: int
    candidate_count: int
    route_evaluation_count: int
    accepted_actions: tuple[str, ...]


def improve_default_days(
    step1: Step1Plan,
    itinerary: ItineraryPlan,
    provider: TravelTimeProvider,
    weather: dict[date, DailyWeather],
) -> ScheduleOptimizationResult:
    """Improve real routed load, not the nominal pre-feasibility cluster sizes."""
    bases = {d.visit_date: d for d in step1.days}
    search_started = perf_counter()
    allocations = {a.attraction.id: a for d in step1.days for a in d.allocations}
    dates = tuple(sorted(bases))
    context = build_review_context(
        (allocation.attraction for allocation in allocations.values()),
        itinerary,
        travel_mode=step1.travel_mode,
    )
    initial_review = (
        evaluate_routed_experience(
            itinerary.days,
            context,
            provider,
            meal_by_date={
                item.routed_day.visit_date.isoformat(): item.meal_plan
                for item in itinerary.segmented_days
            },
        )
        if itinerary.valid
        else None
    )
    if len(dates) < 2 or not itinerary.valid:
        return ScheduleOptimizationResult(
            step1,
            initial_review,
            initial_review,
            (
                OptimizationStopReason.NO_NEW_CANDIDATE
                if itinerary.valid
                else OptimizationStopReason.NO_FEASIBLE_SEED
            ),
            0,
            0,
            0,
            (),
        )
    current = tuple(tuple(sorted(v.attraction.id for v in d.visits)) for d in itinerary.days)
    ids = tuple(sorted(i for group in current for i in group))
    if not ids:
        return ScheduleOptimizationResult(
            step1,
            initial_review,
            initial_review,
            OptimizationStopReason.NO_NEW_CANDIDATE,
            0,
            0,
            0,
            (),
        )
    all_close_pairs = []
    for a, b in combinations(ids, 2):
        if _is_close_pair(a, b, allocations, provider):
            all_close_pairs.append((a, b))
    cache: dict[tuple[int, tuple[int, ...]], SegmentedDay | None] = {}

    def routed(index: int, members: tuple[int, ...]) -> SegmentedDay | None:
        key = (index, members)
        if key not in cache:
            if len(cache) >= QUALITY_ROUTE_BUDGET:
                return None
            base = bases[dates[index]]
            items = tuple(replace(allocations[i], assigned_date=dates[index]) for i in members)
            if any(_precheck_target(a, dates[index], base, weather) for a in items):
                cache[key] = None
            else:
                candidate = route_segmented_day(
                    rebuild_day_plan(base, items, step1.travel_mode),
                    provider,
                    weather_by_date=weather,
                    travel_mode=step1.travel_mode,
                )
                cache[key] = (
                    candidate
                    if candidate.validation.valid and not candidate.routed_day.unplaced
                    else None
                )
        return cache[key]

    def score(
        partition: tuple[tuple[int, ...], ...],
    ) -> ItineraryExperienceReview | None:
        days = [routed(index, members) for index, members in enumerate(partition)]
        if any(d is None for d in days):
            return None
        feasible_days = tuple(day for day in days if day is not None)
        return evaluate_routed_experience(
            tuple(day.routed_day for day in feasible_days),
            context,
            provider,
            meal_by_date={
                day.routed_day.visit_date.isoformat(): day.meal_plan for day in feasible_days
            },
        )

    best_score = score(current)
    if best_score is None:
        return ScheduleOptimizationResult(
            step1,
            initial_review,
            None,
            OptimizationStopReason.NO_FEASIBLE_SEED,
            0,
            0,
            len(cache),
            (),
        )
    if best_score.quality_target_met:
        return ScheduleOptimizationResult(
            step1,
            initial_review,
            best_score,
            OptimizationStopReason.QUALITY_TARGET_MET,
            0,
            0,
            len(cache),
            (),
        )
    visited = {current}
    accepted_actions: list[str] = []
    candidate_count = 0
    rounds = 0
    stop_reason = OptimizationStopReason.ROUND_BUDGET
    for round_index in range(QUALITY_MAX_PASSES):
        rounds = round_index + 1
        candidates = set()
        bundles: list[tuple[int, ...]] = []
        for group in current:
            pending = set(group)
            for i in group:
                bundles.append((i,))
            while pending:
                component = {min(pending)}
                while True:
                    expanded = (
                        component
                        | {b for a, b in all_close_pairs if a in component and b in pending}
                        | {a for a, b in all_close_pairs if b in component and a in pending}
                    )
                    if expanded == component:
                        break
                    component = expanded
                pending -= component
                if len(component) > 1:
                    bundles.append(tuple(sorted(component)))
        for bundle in bundles:
            source = next(k for k, g in enumerate(current) if bundle[0] in g)
            for target in range(len(dates)):
                if source == target:
                    continue
                proposal = [set(g) for g in current]
                proposal[source] -= set(bundle)
                proposal[target] |= set(bundle)
                candidates.add(tuple(tuple(sorted(g)) for g in proposal))
                target_bundles = [other for other in bundles if other[0] in current[target]]
                return_groups = [(other,) for other in target_bundles] + [
                    pair
                    for pair in combinations(target_bundles, 2)
                    if set(pair[0]).isdisjoint(pair[1])
                ]
                for return_group in return_groups:
                    returning = set().union(*(set(other) for other in return_group))
                    swapped = [set(g) for g in proposal]
                    swapped[target] -= returning
                    swapped[source] |= returning
                    candidates.add(tuple(tuple(sorted(g)) for g in swapped))
        # A split neighbour may require one move plus a two-node return group
        # to preserve meals and daily load. Generate that transaction directly
        # so the search does not have to accept a worse intermediate state.
        day_by_id = {
            attraction_id: day_index
            for day_index, group in enumerate(current)
            for attraction_id in group
        }
        for left, right in all_close_pairs:
            left_day, right_day = day_by_id[left], day_by_id[right]
            if left_day == right_day:
                continue
            for moving, source, target in (
                (left, left_day, right_day),
                (right, right_day, left_day),
            ):
                returnable = tuple(item for item in current[target] if item != moving)
                for return_count in (1, 2):
                    for returning_ids in combinations(returnable, return_count):
                        proposal = [set(group) for group in current]
                        proposal[source].remove(moving)
                        proposal[target].add(moving)
                        proposal[target] -= set(returning_ids)
                        proposal[source] |= set(returning_ids)
                        candidates.add(tuple(tuple(sorted(group)) for group in proposal))
        candidates -= visited
        if not candidates:
            stop_reason = OptimizationStopReason.NO_NEW_CANDIDATE
            break
        winner, winner_score = current, best_score
        ordered_candidates = sorted(
            candidates,
            key=lambda item: _cheap_candidate_key(
                item,
                all_close_pairs,
                allocations,
                bases,
                dates,
                provider,
            ),
        )[:QUALITY_CANDIDATES_PER_ROUND]
        for candidate in ordered_candidates:
            if perf_counter() - search_started >= QUALITY_WALL_TIME_LIMIT_SECONDS:
                stop_reason = OptimizationStopReason.WALL_TIME_LIMIT
                break
            if len(cache) >= QUALITY_ROUTE_BUDGET:
                stop_reason = OptimizationStopReason.ROUTE_BUDGET
                break
            visited.add(candidate)
            candidate_count += 1
            candidate_score = score(candidate)
            if candidate_score is not None and candidate_score.rank_key < winner_score.rank_key:
                winner, winner_score = candidate, candidate_score
        if winner == current:
            if stop_reason not in {
                OptimizationStopReason.ROUTE_BUDGET,
                OptimizationStopReason.WALL_TIME_LIMIT,
            }:
                stop_reason = OptimizationStopReason.NO_IMPROVEMENT
            break
        accepted_actions.append(_describe_action(current, winner))
        current, best_score = winner, winner_score
        if best_score.quality_target_met:
            stop_reason = OptimizationStopReason.QUALITY_TARGET_MET
            break

    # Retain rejected input accounting; routed drops remain available for the
    # existing recovery pass and are not silently forgotten.
    retained = set(ids)
    extra = {
        day.visit_date: [a for a in day.allocations if a.attraction.id not in retained]
        for day in step1.days
    }
    plan = replace(
        step1,
        days=tuple(
            rebuild_day_plan(
                bases[day],
                (
                    *(replace(allocations[i], assigned_date=day) for i in current[index]),
                    *extra[day],
                ),
                step1.travel_mode,
            )
            for index, day in enumerate(dates)
        ),
    )
    return ScheduleOptimizationResult(
        plan,
        initial_review,
        best_score,
        stop_reason,
        rounds,
        candidate_count,
        len(cache),
        tuple(accepted_actions),
    )


def _is_close_pair(
    left: int,
    right: int,
    allocations: dict[int, DayAllocation],
    provider: TravelTimeProvider,
) -> bool:
    forward = provider.get_travel_time(left, right)
    backward = provider.get_travel_time(right, left)
    if forward is None or backward is None:
        return False
    if forward.travel_min + backward.travel_min <= QUALITY_NEIGHBOUR_SYMMETRIC_MIN:
        return True
    distances = [item.distance_m for item in (forward, backward) if item.distance_m is not None]
    return (
        bool(distances)
        and min(distances) <= QUALITY_NEIGHBOUR_DISTANCE_M
        and not allocations[left].attraction.is_indoor
        and not allocations[right].attraction.is_indoor
    )


def _describe_action(
    before: tuple[tuple[int, ...], ...], after: tuple[tuple[int, ...], ...]
) -> str:
    moved = sorted(
        attraction_id
        for attraction_id in {item for group in before for item in group}
        if next(index for index, group in enumerate(before) if attraction_id in group)
        != next(index for index, group in enumerate(after) if attraction_id in group)
    )
    if len(moved) == 1:
        return f"move:{moved[0]}"
    if len(moved) == 2:
        return f"swap:{moved[0]}:{moved[1]}"
    return "group_move:" + ":".join(str(item) for item in moved)


def _split_neighbour_count(
    partition: tuple[tuple[int, ...], ...],
    close_pairs: list[tuple[int, int]],
) -> int:
    day_by_id = {
        attraction_id: day_index
        for day_index, group in enumerate(partition)
        for attraction_id in group
    }
    return sum(day_by_id[left] != day_by_id[right] for left, right in close_pairs)


def _cheap_candidate_key(
    partition: tuple[tuple[int, ...], ...],
    close_pairs: list[tuple[int, int]],
    allocations: dict[int, DayAllocation],
    bases: dict[date, DayPlan],
    dates: tuple[date, ...],
    provider: TravelTimeProvider,
) -> tuple[int, int, int, int, tuple[tuple[int, ...], ...]]:
    load_rates = []
    for index, members in enumerate(partition):
        base = bases[dates[index]]
        available = max(1, base.bounds.end_min - base.bounds.start_min)
        suggested = sum(allocations[item].attraction.suggested_duration for item in members)
        load_rates.append(suggested * 1000 // available)
    return (
        _split_neighbour_count(partition, close_pairs),
        _tight_fixed_connection_count(partition, allocations, dates, provider),
        max(load_rates) - min(load_rates),
        sum(_minimum_spanning_travel(group, provider) for group in partition),
        partition,
    )


def _tight_fixed_connection_count(
    partition: tuple[tuple[int, ...], ...],
    allocations: dict[int, DayAllocation],
    dates: tuple[date, ...],
    provider: TravelTimeProvider,
) -> int:
    """Prioritize exact routing for partitions that separate tight fixed events."""

    count = 0
    for day_index, members in enumerate(partition):
        visit_date = dates[day_index]
        fixed = []
        for attraction_id in members:
            sessions = tuple(
                session
                for session in allocations[attraction_id].attraction.fixed_sessions
                if session.matches(visit_date)
            )
            if sessions:
                fixed.append((attraction_id, sessions))
        for (left_id, left_sessions), (right_id, right_sessions) in combinations(fixed, 2):
            travel = provider.get_travel_time(left_id, right_id)
            reverse = provider.get_travel_time(right_id, left_id)
            slacks: list[int] = []
            if travel is not None:
                slacks.extend(
                    right.entry_min - left.end_min - travel.travel_min
                    for left in left_sessions
                    for right in right_sessions
                    if left.end_min <= right.entry_min
                )
            if reverse is not None:
                slacks.extend(
                    left.entry_min - right.end_min - reverse.travel_min
                    for left in left_sessions
                    for right in right_sessions
                    if right.end_min <= left.entry_min
                )
            if not slacks or max(slacks) < QUALITY_FIXED_CONNECTION_SEVERE_MIN:
                count += 1
    return count


def _minimum_spanning_travel(members: tuple[int, ...], provider: TravelTimeProvider) -> int:
    if len(members) < 2:
        return 0
    connected = {min(members)}
    remaining = set(members) - connected
    total = 0
    while remaining:
        edges = []
        for left in connected:
            for right in remaining:
                forward = provider.get_travel_time(left, right)
                backward = provider.get_travel_time(right, left)
                if forward is None or backward is None:
                    continue
                edges.append((forward.travel_min + backward.travel_min, left, right))
        if not edges:
            return 1_000_000
        cost, _left, right = min(edges)
        total += cost
        connected.add(right)
        remaining.remove(right)
    return total
