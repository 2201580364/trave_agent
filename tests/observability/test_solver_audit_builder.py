"""Solver audit builder tests. Traceability: H3, H7, ADR-0005 D4."""

from datetime import UTC, date, datetime

from travel_agent.observability import SolverRunStatus, build_solver_run_audit
from travel_agent.solver import (
    Attraction,
    DayTimeBounds,
    ItineraryPlan,
    ItineraryReassignment,
    RouteValidation,
    RouteVisit,
    RoutedDay,
    TimeBucket,
    VisitPeriodPreference,
    evaluate_visit_period,
    evaluate_solver_quality,
)


DAY = date(2026, 8, 24)


def test_audit_builder_serializes_assignments_reassignments_and_counts() -> None:
    attraction = Attraction(1, "景点", data_verified=True)
    routed = RoutedDay(
        DAY,
        DayTimeBounds(9 * 60, 18 * 60),
        (RouteVisit(attraction, 9 * 60, 9 * 60 + 36, 36),),
        (),
        0,
        0,
    )
    itinerary = ItineraryPlan(
        (routed,),
        (),
        (),
        (ItineraryReassignment(attraction, DAY, date(2026, 8, 25)),),
        (RouteValidation(True),),
        True,
    )
    quality = evaluate_solver_quality(itinerary, [attraction])

    audit = build_solver_run_audit(
        itinerary,
        quality,
        solve_run_id="solve-1",
        solver_version="0.1.0",
        constraint_version="ADR-0004",
        parameter_version="p1-v1",
        input_snapshot_hash="sha256:abc",
        data_snapshot_version="hz-v1",
        od_basis="gaode",
        weather_basis="forecast",
        random_seed=0,
        duration_ratio=0.6,
        elapsed_ms=25,
        created_at=datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
    )
    payload = audit.to_dict()

    assert audit.status is SolverRunStatus.COMPLETED
    assert audit.hard_constraint_violations == 0
    assert payload["input_count"] == 1
    assert payload["scheduled_count"] == 1
    assert [event["outcome"] for event in payload["events"]] == [
        "assigned",
        "reassigned",
    ]
    assert payload["events"][0]["visit_date"] == "2026-08-24"
    assert payload["events"][1]["to_date"] == "2026-08-25"


def test_audit_builder_records_explainable_visit_period_decision() -> None:
    attraction = Attraction(1, "河坊街", data_verified=True)
    preference = VisitPeriodPreference(
        frozenset({TimeBucket.EVENING}),
        frozenset({TimeBucket.AFTERNOON}),
        source_ref="CURATOR-HZ-1",
    )
    evaluation = evaluate_visit_period(10 * 60, preference)
    routed = RoutedDay(
        DAY,
        DayTimeBounds(9 * 60, 18 * 60),
        (
            RouteVisit(
                attraction,
                10 * 60,
                10 * 60 + 36,
                36,
                visit_period=evaluation,
            ),
        ),
        (),
        0,
        0,
    )
    itinerary = ItineraryPlan(
        (routed,),
        (),
        (),
        (),
        (RouteValidation(True),),
        True,
    )
    quality = evaluate_solver_quality(itinerary, [attraction])

    audit = build_solver_run_audit(
        itinerary,
        quality,
        solve_run_id="solve-period-1",
        solver_version="0.1.0",
        constraint_version="ADR-0008",
        parameter_version="period-cost-v1",
        input_snapshot_hash="sha256:period",
        data_snapshot_version="hz-v1",
        od_basis="gaode",
        weather_basis="forecast",
        random_seed=0,
        duration_ratio=0.6,
        elapsed_ms=25,
        created_at=datetime(2026, 8, 23, 8, 0, tzinfo=UTC),
    )
    event = next(item for item in audit.to_dict()["events"] if item["constraint"] == "VISIT_PERIOD")

    assert event["outcome"] == "fallback"
    assert event["preference_source"] == "curated"
    assert event["preference_source_ref"] == "CURATOR-HZ-1"
    assert event["preferred_bucket"] == "evening"
    assert event["acceptable_buckets"] == ["afternoon"]
    assert event["actual_bucket"] == "morning"
    assert event["deviation_min"] == 420
    assert event["travel_cost_scale"] == 30
    assert event["period_deviation_cost"] == 1
