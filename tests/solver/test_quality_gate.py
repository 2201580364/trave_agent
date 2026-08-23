"""Itinerary quality gate tests. Traceability: H3, C1, C2, C4, C5, C6, G5/G6."""

from datetime import date

import pytest

from travel_agent.solver import (
    Attraction,
    ConstraintName,
    ConstraintViolation,
    DayTimeBounds,
    ItineraryPlan,
    ItineraryUnplaced,
    RejectedAttraction,
    RejectionCode,
    RouteValidation,
    RouteVisit,
    RoutedDay,
    evaluate_solver_quality,
)


DAY = date(2026, 8, 24)


def _attraction(attraction_id: int) -> Attraction:
    return Attraction(attraction_id, f"景点 {attraction_id}", data_verified=True)


def _routed_day(*attractions: Attraction) -> RoutedDay:
    visits = tuple(
        RouteVisit(item, 9 * 60 + index * 60, 9 * 60 + index * 60 + 36, 36)
        for index, item in enumerate(attractions)
    )
    return RoutedDay(DAY, DayTimeBounds(9 * 60, 18 * 60), visits, (), 0, 0)


def test_quality_gate_proves_scheduled_unplaced_rejected_conservation() -> None:
    scheduled, unplaced, rejected = _attraction(1), _attraction(2), _attraction(3)
    itinerary = ItineraryPlan(
        (_routed_day(scheduled),),
        (ItineraryUnplaced(unplaced, DAY, RejectionCode.NO_AVAILABLE_DATE),),
        (RejectedAttraction(rejected, RejectionCode.DATA_UNVERIFIED),),
        (),
        (RouteValidation(True),),
        True,
    )

    report = evaluate_solver_quality(itinerary, [scheduled, unplaced, rejected])

    assert report.accounting.conserved
    assert report.accounting.input_count == 3
    assert report.accounting.scheduled_count == 1
    assert report.accounting.unplaced_count == 1
    assert report.accounting.data_rejected_count == 1
    assert report.hard_constraint_violations == 0
    assert report.gate_passed


def test_quality_gate_detects_duplicate_and_missing_attractions() -> None:
    duplicated, missing = _attraction(1), _attraction(2)
    itinerary = ItineraryPlan(
        (_routed_day(duplicated),),
        (ItineraryUnplaced(duplicated, DAY, RejectionCode.NO_AVAILABLE_DATE),),
        (),
        (),
        (RouteValidation(True),),
        True,
    )

    report = evaluate_solver_quality(itinerary, [duplicated, missing])

    assert not report.accounting.conserved
    assert report.accounting.duplicate_ids == (1,)
    assert report.accounting.missing_ids == (2,)
    assert not report.gate_passed


def test_quality_gate_counts_each_hard_constraint_family() -> None:
    attraction = _attraction(1)
    validation = RouteValidation(
        False,
        (
            ConstraintViolation(RejectionCode.CLOSED_ON_DATE, 1),
            ConstraintViolation(RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL, 1),
            ConstraintViolation(RejectionCode.ANCHOR_VIOLATION, 1),
            ConstraintViolation(RejectionCode.EXTREME_WEATHER_OUTDOOR, 1),
            ConstraintViolation(RejectionCode.TRANSIT_INFEASIBLE, 1),
        ),
    )
    itinerary = ItineraryPlan(
        (_routed_day(attraction),),
        (),
        (),
        (),
        (validation,),
        False,
    )

    report = evaluate_solver_quality(itinerary, [attraction])
    counts = {item.constraint: item.count for item in report.hard_constraint_counts}

    assert counts[ConstraintName.C1] == 1
    assert counts[ConstraintName.C2] == 1
    assert counts[ConstraintName.C4] == 1
    assert counts[ConstraintName.C5] == 1
    assert counts[ConstraintName.C6] == 1
    assert report.hard_constraint_violations == 5
    assert not report.gate_passed


def test_quality_gate_rejects_duplicate_input_ids() -> None:
    attraction = _attraction(1)
    itinerary = ItineraryPlan(
        (_routed_day(attraction),),
        (),
        (),
        (),
        (RouteValidation(True),),
        True,
    )

    with pytest.raises(ValueError, match="input attraction ids"):
        evaluate_solver_quality(itinerary, [attraction, attraction])
