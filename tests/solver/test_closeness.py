"""Reviewed itinerary closeness tests. Traceability: H3, Gate 6, ADR-0007."""

from datetime import date

import pytest

from travel_agent.solver import (
    AdjacencyExpectation,
    Attraction,
    BaselineProvenance,
    DayTimeBounds,
    ExpectationOutcome,
    ItineraryBaseline,
    ItineraryPlan,
    RouteValidation,
    RouteVisit,
    RoutedDay,
    SameDayExpectation,
    TimeBucket,
    VisitExpectation,
    evaluate_itinerary_closeness,
    evaluate_solver_quality,
)


MONDAY = date(2026, 8, 24)
TUESDAY = date(2026, 8, 25)


def _attraction(attraction_id: int) -> Attraction:
    return Attraction(attraction_id, f"Attraction {attraction_id}", data_verified=True)


def _itinerary(*days: tuple[date, tuple[tuple[Attraction, int], ...]]) -> ItineraryPlan:
    routed_days = tuple(
        RoutedDay(
            visit_date,
            DayTimeBounds(8 * 60, 22 * 60),
            tuple(
                RouteVisit(attraction, arrival, arrival + 60, 60)
                for attraction, arrival in visits
            ),
            (),
            0,
            0,
        )
        for visit_date, visits in days
    )
    return ItineraryPlan(
        routed_days,
        (),
        (),
        (),
        tuple(RouteValidation(True) for _ in routed_days),
        True,
    )


def _baseline(**changes: object) -> ItineraryBaseline:
    values = {
        "baseline_id": "reviewed-1",
        "version": "1.0.0",
        "provenance": BaselineProvenance.HUMAN_REVIEWED,
        "source_refs": ("REVIEW-1",),
        "visit_expectations": (),
        "same_day_expectations": (),
        "adjacency_expectations": (),
    }
    values.update(changes)
    return ItineraryBaseline(**values)


def _evaluate(itinerary: ItineraryPlan, baseline: ItineraryBaseline):
    attractions = [visit.attraction for day in itinerary.days for visit in day.visits]
    quality = evaluate_solver_quality(itinerary, attractions)
    return evaluate_itinerary_closeness(itinerary, quality, baseline)


def test_exact_reviewed_baseline_scores_every_component_as_one() -> None:
    first, second = _attraction(1), _attraction(2)
    itinerary = _itinerary((MONDAY, ((first, 9 * 60), (second, 13 * 60))))
    baseline = _baseline(
        visit_expectations=(
            VisitExpectation(1, MONDAY, preferred_buckets=frozenset({TimeBucket.MORNING})),
            VisitExpectation(2, MONDAY, preferred_buckets=frozenset({TimeBucket.AFTERNOON})),
        ),
        same_day_expectations=(SameDayExpectation(frozenset({1, 2})),),
        adjacency_expectations=(AdjacencyExpectation(1, 2, directional=True),),
    )

    report = _evaluate(itinerary, baseline)

    assert report.source_refs == ("REVIEW-1",)
    assert report.fixed_visit_score == 1
    assert report.day_assignment.score == 1
    assert report.time_bucket.score == 1
    assert report.same_day.score == 1
    assert report.adjacency.score == 1
    assert len(report.expectation_outcomes) == 6
    assert all(item.score == 1 for item in report.expectation_outcomes)
    assert report.overall_closeness == 1
    assert report.baseline_passed


def test_acceptable_non_preferred_day_and_bucket_score_point_seven() -> None:
    attraction = _attraction(1)
    itinerary = _itinerary((TUESDAY, ((attraction, 14 * 60),)))
    baseline = _baseline(
        visit_expectations=(
            VisitExpectation(
                1,
                MONDAY,
                frozenset({TUESDAY}),
                frozenset({TimeBucket.MORNING}),
                frozenset({TimeBucket.AFTERNOON}),
            ),
        ),
    )

    report = _evaluate(itinerary, baseline)

    assert report.day_assignment.score == pytest.approx(0.7)
    assert report.time_bucket.score == pytest.approx(0.7)
    assert report.overall_closeness == pytest.approx(0.7)
    assert tuple(item.outcome for item in report.expectation_outcomes) == (
        ExpectationOutcome.ACCEPTABLE,
        ExpectationOutcome.ACCEPTABLE,
    )
    assert not report.baseline_passed


@pytest.mark.parametrize(
    ("directional", "expected"),
    ((False, 1.0), (True, 0.0)),
)
def test_adjacency_direction_is_explicit(directional: bool, expected: float) -> None:
    first, second = _attraction(1), _attraction(2)
    itinerary = _itinerary((MONDAY, ((second, 9 * 60), (first, 11 * 60))))
    baseline = _baseline(
        adjacency_expectations=(AdjacencyExpectation(1, 2, directional),),
    )

    assert _evaluate(itinerary, baseline).adjacency.score == expected


def test_fixed_miss_and_hard_gate_cannot_be_compensated() -> None:
    attraction = _attraction(1)
    itinerary = _itinerary((TUESDAY, ((attraction, 9 * 60),)))
    baseline = _baseline(
        visit_expectations=(VisitExpectation(1, MONDAY, fixed_day=True),),
    )
    quality = evaluate_solver_quality(itinerary, [attraction])
    fixed_miss = evaluate_itinerary_closeness(itinerary, quality, baseline, threshold=0)

    assert fixed_miss.overall_closeness == 0
    assert fixed_miss.fixed_visit_score == 0
    assert not fixed_miss.baseline_passed

    hard_failed_quality = evaluate_solver_quality(
        itinerary,
        [attraction, _attraction(2)],
    )
    exact_baseline = _baseline(
        visit_expectations=(VisitExpectation(1, TUESDAY, fixed_day=True),),
    )
    hard_failed = evaluate_itinerary_closeness(
        itinerary,
        hard_failed_quality,
        exact_baseline,
    )

    assert hard_failed.fixed_visit_score == 1
    assert hard_failed.overall_closeness == 1
    assert not hard_failed.hard_gate_passed
    assert not hard_failed.baseline_passed


def test_missing_attraction_scores_zero() -> None:
    present = _attraction(1)
    itinerary = _itinerary((MONDAY, ((present, 9 * 60),)))
    baseline = _baseline(
        visit_expectations=(VisitExpectation(99, MONDAY),),
    )

    report = _evaluate(itinerary, baseline)

    assert report.day_assignment.score == 0
    assert report.overall_closeness == 0
    assert report.expectation_outcomes[0].actual_values == ()
    assert report.expectation_outcomes[0].outcome is ExpectationOutcome.MISSING


def test_baseline_rejects_duplicates_and_empty_expectations() -> None:
    with pytest.raises(ValueError, match="unique attraction ids"):
        _baseline(
            visit_expectations=(VisitExpectation(1, MONDAY), VisitExpectation(1, TUESDAY)),
        )
    with pytest.raises(ValueError, match="at least one scored expectation"):
        _baseline()


def test_threshold_is_validated() -> None:
    attraction = _attraction(1)
    itinerary = _itinerary((MONDAY, ((attraction, 9 * 60),)))
    baseline = _baseline(visit_expectations=(VisitExpectation(1, MONDAY),))
    quality = evaluate_solver_quality(itinerary, [attraction])

    with pytest.raises(ValueError, match="threshold"):
        evaluate_itinerary_closeness(itinerary, quality, baseline, threshold=1.01)
