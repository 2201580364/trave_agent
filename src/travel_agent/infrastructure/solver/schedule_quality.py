"""Deterministic whole-trip soft improvement after hard recovery (H3, ADR-0027).

Only used for the gateway's derived default dates, never user-locked dates.
Moves and swaps are rerouted and independently validated before acceptance.
"""

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
from travel_agent.solver.models import DailyWeather, SegmentedDay
from travel_agent.solver.quality_policy import (
    QUALITY_BALANCE_TOLERANCE_PER_MILLE,
    QUALITY_DATE_PERMUTATION_LIMIT,
    QUALITY_EVENING_REST_MIN,
    QUALITY_MAX_PASSES,
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
    # Protect local pairs as a soft priority; singletons and connected groups
    # are both proposed so capacity/availability can still separate them.
    close_pairs = []
    original_day = {i: k for k, group in enumerate(current) for i in group}
    for a, b in combinations(ids, 2):
        ab, ba = provider.get_travel_time(a, b), provider.get_travel_time(b, a)
        if (
            original_day[a] == original_day[b]
            and ab is not None
            and ba is not None
            and ab.travel_min + ba.travel_min <= QUALITY_NEIGHBOUR_SYMMETRIC_MIN
        ):
            close_pairs.append((a, b))
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
        split = sum(index_by_id[a] != index_by_id[b] for a, b in close_pairs)
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
            split,
            meals,
            shortfall,
            tight_evening,
            max(loads) - min(loads),
            travel,
        )

    best_score = score(current)
    if best_score is None:
        return step1
    if (
        best_score[0] == 0
        and best_score[2:5] == (0, 0, 0)
        and best_score[5] <= QUALITY_BALANCE_TOLERANCE_PER_MILLE
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
