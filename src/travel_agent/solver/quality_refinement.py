"""Fixed-order duration and meal refinement; H3/C2/C4/C6, ADR-0027.

Only genuine opening slack is consumed. Order and buffered directed connections
are immutable; an event may select another reviewed session. Failure returns the seed.
"""

from dataclasses import replace

from ortools.sat.python import cp_model

from .models import RoutedDay
from .quality_policy import QUALITY_EVENING_REST_MIN, QUALITY_REFINEMENT_DETERMINISTIC_LIMIT
from .time_windows import applicable_fixed_sessions, resolve_effective_window
from .visit_periods import evaluate_visit_period


def refine_ordered_schedule(route: RoutedDay) -> RoutedDay:
    if not route.visits:
        return route
    model = cp_model.CpModel()
    starts: list[cp_model.IntVar] = []
    ends: list[cp_model.IntVar] = []
    durations: list[cp_model.IntVar] = []
    intervals: list[cp_model.IntervalVar] = []
    horizon = route.bounds.end_min
    for index, visit in enumerate(route.visits):
        start = model.new_int_var(route.bounds.start_min, horizon, f"start_{index}")
        end = model.new_int_var(route.bounds.start_min, horizon, f"end_{index}")
        if visit.attraction.fixed_sessions:
            sessions = [
                s
                for s in applicable_fixed_sessions(visit.attraction, route.visit_date)
                if s.entry_min >= route.bounds.start_min and s.end_min <= horizon
            ]
            if not sessions:
                return route
            duration = model.new_int_var(1, horizon, f"session_duration_{index}")
            model.add_allowed_assignments(
                [start, end, duration],
                [(s.entry_min, s.end_min, s.end_min - s.entry_min) for s in sessions],
            )
        else:
            resolution = resolve_effective_window(visit.attraction, route.visit_date)
            if resolution.window is None:
                return route
            window = resolution.window
            duration = model.new_int_var(
                visit.planned_duration_min,
                max(visit.planned_duration_min, visit.attraction.suggested_duration),
                f"duration_{index}",
            )
            model.add(start >= window.open_min)
            model.add(end <= window.close_min)
            if window.last_entry_min is not None:
                model.add(start <= window.last_entry_min)
        intervals.append(model.new_interval_var(start, duration, end, f"visit_{index}"))
        if index:
            travel = visit.buffered_travel_from_previous_min
            model.add(start >= ends[-1] + travel)
            # A meal cannot consume the incoming transit reservation.
            transit_start = model.new_int_var(0, horizon, f"transit_start_{index}")
            model.add(transit_start == start - travel)
            intervals.append(model.new_interval_var(transit_start, travel, start, f"od_{index}"))
        starts.append(start)
        ends.append(end)
        durations.append(duration)

    meals, meal_starts = [], []
    for name, opening, closing, length in (("lunch", 690, 840, 60), ("dinner", 990, 1320, 90)):
        if max(opening, route.bounds.start_min) + length > min(closing, horizon):
            continue
        present = model.new_bool_var(name)
        start = model.new_int_var(
            max(opening, route.bounds.start_min), min(closing, horizon) - length, name + "_start"
        )
        end = model.new_int_var(0, horizon, name + "_end")
        intervals.append(
            model.new_optional_interval_var(start, length, end, present, name + "_interval")
        )
        meals.append(present)
        meal_starts.append(start)
    model.add_no_overlap(intervals)

    # Lexicographic optimisation: full meals, suggested durations, then compact
    # earliest timing. Integer stages avoid weights that vary with group size.
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_deterministic_time = QUALITY_REFINEMENT_DETERMINISTIC_LIMIT
    first_early = model.new_bool_var("preserve_first_arrival")
    model.add(starts[0] == route.visits[0].arrival_min).only_enforce_if(first_early)
    afternoon = []
    daytime_indices = [
        i
        for i, visit in enumerate(route.visits)
        if not visit.attraction.fixed_sessions
        and (day_window := resolve_effective_window(visit.attraction, route.visit_date).window)
        and day_window.open_min < 1020
    ]
    # Spread a daytime block, rather than delaying only its last nearby node.
    if len(daytime_indices) >= 2:
        for index in daytime_indices[1:]:
            present = model.new_bool_var(f"afternoon_{index}")
            model.add(starts[index] >= 780).only_enforce_if(present)
            afternoon.append(present)
    rests = []
    for index in range(1, len(route.visits)):
        if route.visits[index - 1].arrival_min >= 1020:
            rest = model.new_bool_var(f"evening_rest_{index}")
            model.add(
                starts[index]
                >= ends[index - 1]
                + route.visits[index].buffered_travel_from_previous_min
                + QUALITY_EVENING_REST_MIN
            ).only_enforce_if(rest)
            rests.append(rest)
    flexible_duration = sum(
        d for d, v in zip(durations, route.visits, strict=True) if not v.attraction.fixed_sessions
    )
    for expression in (
        sum(meals),
        flexible_duration,
        first_early,
        sum(rests),
        sum(afternoon),
        -sum(starts) - sum(meal_starts),
    ):
        model.maximize(expression)
        if solver.solve(model) != cp_model.OPTIMAL:
            return route
        model.add(expression == solver.value(expression))
    visits = []
    for index, visit in enumerate(route.visits):
        arrival, leave = solver.value(starts[index]), solver.value(ends[index])
        if visit.attraction.fixed_sessions and not any(
            s.entry_min == arrival and s.end_min == leave
            for s in applicable_fixed_sessions(visit.attraction, route.visit_date)
        ):
            return route
        planned_duration = leave - arrival
        notice = None
        if (
            not visit.attraction.fixed_sessions
            and planned_duration < visit.attraction.suggested_duration
        ):
            notice = (
                f"实际可玩 {planned_duration} 分钟"
                f"（建议 {visit.attraction.suggested_duration} 分钟）"
            )
        visits.append(
            replace(
                visit,
                arrival_min=arrival,
                leave_min=leave,
                planned_duration_min=planned_duration,
                duration_notice=notice,
                visit_period=evaluate_visit_period(arrival, visit.visit_period.preference)
                if visit.visit_period
                else None,
            )
        )
    return replace(route, visits=tuple(visits))
