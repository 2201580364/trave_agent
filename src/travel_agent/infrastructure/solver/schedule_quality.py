"""Deterministic whole-trip soft improvement after hard recovery (H3, ADR-0027).

Only used for the gateway's derived default dates, never user-locked dates.
Moves and swaps are rerouted and independently validated before acceptance.
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from itertools import combinations, permutations

from travel_agent.solver import (
    ItineraryPlan,
    Step1Plan,
    TravelTimeProvider,
)
from travel_agent.solver.day_assignment import rebuild_day_plan
from travel_agent.solver.itinerary import _precheck_target
from travel_agent.solver.models import DailyWeather, DayAllocation, SegmentedDay
from travel_agent.solver.quality_policy import (
    QUALITY_BALANCE_TOLERANCE_PER_MILLE,
    QUALITY_DATE_PERMUTATION_LIMIT,
    QUALITY_EVENING_REST_MIN,
    QUALITY_MAX_PASSES,
    QUALITY_NEIGHBOUR_DISTANCE_M,
    QUALITY_NEIGHBOUR_SYMMETRIC_MIN,
    QUALITY_ROUTE_BUDGET,
)
from travel_agent.solver.segments import route_segmented_day


def improve_default_days(
    step1: Step1Plan,
    itinerary: ItineraryPlan,
    provider: TravelTimeProvider,
    weather: dict[date, DailyWeather],
) -> Step1Plan:
    """Improve real routed load, not the nominal pre-feasibility cluster sizes."""
    bases = {d.visit_date: d for d in step1.days}
    allocations = {a.attraction.id: a for d in step1.days for a in d.allocations}
    dates = tuple(sorted(bases))
    if len(dates) < 2 or not itinerary.valid:
        return step1
    current = tuple(tuple(sorted(v.attraction.id for v in d.visits)) for d in itinerary.days)
    ids = tuple(sorted(i for group in current for i in group))
    if not ids:
        return step1
    # Phase 1 keeps ADR-0027's original broad balancing behaviour: protect
    # neighbour pairs that the seed route already had together. Phase 2 below
    # then performs a narrow local absorption for selected outdoor neighbours
    # that were split before the broad search started.
    original_day = {i: k for k, group in enumerate(current) for i in group}
    all_close_pairs = []
    for a, b in combinations(ids, 2):
        if _is_close_pair(a, b, allocations, provider):
            all_close_pairs.append((a, b))
    close_pairs = [(a, b) for a, b in all_close_pairs if original_day[a] == original_day[b]]
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

    def score(partition: tuple[tuple[int, ...], ...]) -> tuple[int, ...] | None:
        days = [routed(index, members) for index, members in enumerate(partition)]
        if any(d is None for d in days):
            return None
        index_by_id = {i: k for k, group in enumerate(partition) for i in group}
        singleton_days = sum(len(group) == 1 for group in partition)
        split = sum(index_by_id[a] != index_by_id[b] for a, b in close_pairs)
        moved_from_initial = sum(
            original_day[i] != index_by_id[i] for group in partition for i in group
        )
        meals = shortfall = travel = tight_evening = 0
        loads = []
        for day in days:
            assert day is not None
            route = day.routed_day
            # Full lunch must occupy real non-transit slack in 11:30..14:00.
            gaps = (
                [(route.bounds.start_min, route.visits[0].arrival_min)]
                if route.visits
                else [(route.bounds.start_min, route.bounds.end_min)]
            )
            gaps += [
                (a.leave_min, b.arrival_min - b.buffered_travel_from_previous_min)
                for a, b in zip(route.visits, route.visits[1:], strict=False)
            ]
            if route.visits:
                gaps.append((route.visits[-1].leave_min, route.bounds.end_min))
            lunch_possible = route.bounds.start_min <= 780 and route.bounds.end_min >= 750
            if lunch_possible and not any(
                min(end, 840) - max(start, 690) >= 60 for start, end in gaps
            ):
                meals += 1
            if route.bounds.end_min >= 1080 and day.meal_plan.duration_min < 90:
                meals += 1
            shortfall += sum(
                max(0, v.attraction.suggested_duration - v.planned_duration_min)
                for v in route.visits
                if not v.attraction.fixed_sessions
            )
            tight_evening += sum(
                a.arrival_min >= 1020
                and b.arrival_min - a.leave_min - b.buffered_travel_from_previous_min
                < QUALITY_EVENING_REST_MIN
                for a, b in zip(route.visits, route.visits[1:], strict=False)
            )
            load = (
                sum(v.planned_duration_min for v in route.visits) + route.total_buffered_travel_min
            )
            loads.append(load * 1000 // max(1, route.bounds.end_min - route.bounds.start_min))
            travel += route.total_travel_min
        return (
            sum(not group for group in partition),
            singleton_days,
            split,
            meals,
            shortfall,
            tight_evening,
            max(loads) - min(loads),
            moved_from_initial,
            travel,
        )

    best_score = score(current)
    if best_score is None:
        return step1
    index_by_id = {i: k for k, group in enumerate(current) for i in group}
    all_neighbours_kept = all(index_by_id[a] == index_by_id[b] for a, b in all_close_pairs)
    if (
        all_neighbours_kept
        and best_score[0] == 0
        and best_score[1] == 0
        and best_score[2] == 0
        and best_score[3:6] == (0, 0, 0)
        and best_score[6] <= QUALITY_BALANCE_TOLERANCE_PER_MILLE
    ):
        return step1
    # Strictly improving bounded descent; memoized date/subset routes cap work.
    for _ in range(min(len(ids), QUALITY_MAX_PASSES)):
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
                        | {b for a, b in close_pairs if a in component and b in pending}
                        | {a for a, b in close_pairs if b in component and a in pending}
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
                for other in bundles:
                    if other[0] not in current[target]:
                        continue
                    swapped = [set(g) for g in proposal]
                    swapped[target] -= set(other)
                    swapped[source] |= set(other)
                    candidates.add(tuple(tuple(sorted(g)) for g in swapped))
        winner, winner_score = current, best_score
        # A late-event cluster may need an earlier date while a daytime group
        # takes the shorter departure day. Evaluate these as one transaction.
        if len(dates) <= QUALITY_DATE_PERMUTATION_LIMIT:
            candidates = {p for c in candidates for p in permutations(c)}
        for candidate in sorted(candidates):
            candidate_score = score(candidate)
            if candidate_score is not None and candidate_score < winner_score:
                winner, winner_score = candidate, candidate_score
        if winner == current:
            break
        current, best_score = winner, winner_score
    current, best_score = _absorb_split_neighbours(
        current,
        best_score,
        all_close_pairs,
        score,
    )

    # Retain rejected input accounting; routed drops remain available for the
    # existing recovery pass and are not silently forgotten.
    retained = set(ids)
    extra = {
        day.visit_date: [a for a in day.allocations if a.attraction.id not in retained]
        for day in step1.days
    }
    return replace(
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


def _absorb_split_neighbours(
    current: tuple[tuple[int, ...], ...],
    best_score: tuple[int, ...],
    close_pairs: list[tuple[int, int]],
    score: Callable[[tuple[tuple[int, ...], ...]], tuple[int, ...] | None],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]]:
    def local_key(
        partition: tuple[tuple[int, ...], ...],
        base_score: tuple[int, ...],
    ) -> tuple[int, ...]:
        index_by_id = {i: k for k, group in enumerate(partition) for i in group}
        split = sum(index_by_id[a] != index_by_id[b] for a, b in close_pairs)
        return (
            base_score[0],
            base_score[1],
            split,
            base_score[3],
            base_score[4],
            base_score[5],
            base_score[6],
            base_score[7],
            base_score[8],
        )

    scorer = score
    best_local_key = local_key(current, best_score)
    for _ in range(QUALITY_MAX_PASSES):
        index_by_id = {i: k for k, group in enumerate(current) for i in group}
        candidates = set()
        for left, right in close_pairs:
            left_day = index_by_id[left]
            right_day = index_by_id[right]
            if left_day == right_day:
                continue
            moves = ((left, left_day, right_day), (right, right_day, left_day))
            for moving, source, target in moves:
                proposal = [set(group) for group in current]
                proposal[source].remove(moving)
                proposal[target].add(moving)
                candidates.add(tuple(tuple(sorted(group)) for group in proposal))
        winner, winner_score, winner_key = current, best_score, best_local_key
        for candidate in sorted(candidates):
            candidate_score = scorer(candidate)
            if candidate_score is None:
                continue
            candidate_key = local_key(candidate, candidate_score)
            if candidate_key < winner_key:
                winner, winner_score, winner_key = candidate, candidate_score, candidate_key
        if winner == current:
            return current, best_score
        current, best_score, best_local_key = winner, winner_score, winner_key
    return current, best_score
