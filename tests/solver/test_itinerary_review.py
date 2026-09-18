"""Expert itinerary review tests. Traceability: H2, H3, H7, S1, S2, ADR-0028."""

from datetime import UTC, date, datetime

from travel_agent.solver import (
    Attraction,
    DayTimeBounds,
    InMemoryTravelTimeProvider,
    ItineraryPlan,
    ODBasis,
    ODTravelMode,
    RoutedDay,
    RouteValidation,
    RouteVisit,
    TravelTimeResult,
)
from travel_agent.solver.itinerary_review import (
    SCORING_POLICY_VERSION,
    WEIGHT_PROFILE_VERSION,
    DiagnosticSeverity,
    build_review_context,
    evaluate_itinerary_experience,
)

DAY = date(2026, 9, 30)
NOW = datetime(2026, 9, 18, tzinfo=UTC)


def _place(place_id: int, *, duration: int = 60, energy: int = 2) -> Attraction:
    return Attraction(
        place_id,
        f"place-{place_id}",
        suggested_duration=duration,
        energy_level=energy,
        is_always_open=True,
        data_verified=True,
    )


def _travel(origin: int, destination: int, minutes: int) -> TravelTimeResult:
    return TravelTimeResult(
        origin,
        destination,
        minutes,
        ODBasis.GAODE,
        "review-test-v1",
        NOW,
        ODTravelMode.WALKING if minutes <= 10 else ODTravelMode.DRIVING,
        minutes * 100,
    )


def _provider(minutes: dict[tuple[int, int], int]) -> InMemoryTravelTimeProvider:
    return InMemoryTravelTimeProvider(
        {pair: _travel(*pair, value) for pair, value in minutes.items()}
    )


def _day(day_offset: int, visits: tuple[tuple[Attraction, int, int], ...]) -> RoutedDay:
    routed = []
    total = 0
    for index, (place, arrival, duration) in enumerate(visits):
        travel = None
        buffered = 0
        if index:
            previous = visits[index - 1][0]
            minutes = max(1, arrival - (visits[index - 1][1] + visits[index - 1][2]))
            travel = _travel(previous.id, place.id, minutes)
            buffered = minutes
            total += minutes
        routed.append(RouteVisit(place, arrival, arrival + duration, duration, travel, buffered))
    return RoutedDay(
        DAY.fromordinal(DAY.toordinal() + day_offset),
        DayTimeBounds(9 * 60, 22 * 60),
        tuple(routed),
        (),
        total,
        total,
    )


def _itinerary(*days: RoutedDay) -> ItineraryPlan:
    return ItineraryPlan(
        tuple(days),
        (),
        (),
        (),
        tuple(RouteValidation(True) for _ in days),
        True,
    )


def test_review_detects_split_neighbours_and_prefers_grouped_route() -> None:
    lake, bridge, remote, market = (_place(index) for index in range(1, 5))
    provider = _provider(
        {
            (1, 2): 4,
            (2, 1): 4,
            (1, 3): 35,
            (3, 1): 35,
            (1, 4): 30,
            (4, 1): 30,
            (2, 3): 34,
            (3, 2): 34,
            (2, 4): 29,
            (4, 2): 29,
            (3, 4): 12,
            (4, 3): 12,
        }
    )
    split = _itinerary(
        _day(0, ((lake, 540, 60), (remote, 660, 60))),
        _day(1, ((bridge, 540, 60), (market, 660, 60))),
    )
    grouped = _itinerary(
        _day(0, ((lake, 540, 60), (bridge, 604, 60))),
        _day(1, ((remote, 540, 60), (market, 612, 60))),
    )
    context = build_review_context((lake, bridge, remote, market), split)

    split_review = evaluate_itinerary_experience(split, context, provider)
    grouped_review = evaluate_itinerary_experience(grouped, context, provider)

    assert "NEIGHBOUR_SPLIT" in {item.code for item in split_review.diagnostics}
    assert "NEIGHBOUR_SPLIT" not in {item.code for item in grouped_review.diagnostics}
    assert grouped_review.rank_key < split_review.rank_key


def test_review_separates_hard_gate_from_severe_experience_deficits() -> None:
    museum = _place(1, duration=120)
    bridge = _place(2, duration=60)
    itinerary = _itinerary(
        _day(0, ((museum, 540, 60), (bridge, 610, 30))),
        _day(1, ()),
    )
    provider = _provider({(1, 2): 10, (2, 1): 10})
    review = evaluate_itinerary_experience(
        itinerary,
        build_review_context((museum, bridge), itinerary),
        provider,
    )

    assert review.score_basis_points < 9000
    assert review.severe_issue_count > 0
    assert any(
        item.code == "VISIT_SHORTFALL" and item.severity is DiagnosticSeverity.SEVERE
        for item in review.diagnostics
    )
    assert any(item.code == "LOAD_IMBALANCE" for item in review.diagnostics)


def test_review_is_versioned_deterministic_and_exposes_raw_dimensions() -> None:
    first, second = _place(1), _place(2)
    itinerary = _itinerary(_day(0, ((first, 540, 60), (second, 605, 60))))
    provider = _provider({(1, 2): 5, (2, 1): 5})
    context = build_review_context((first, second), itinerary)

    left = evaluate_itinerary_experience(itinerary, context, provider)
    right = evaluate_itinerary_experience(itinerary, context, provider)

    assert left == right
    assert left.scoring_policy_version == SCORING_POLICY_VERSION
    assert left.weight_profile_version == WEIGHT_PROFILE_VERSION
    assert {item.dimension.value for item in left.dimensions} == {"G", "V", "P", "R", "M", "F", "U"}
    assert sum(item.weight for item in left.dimensions) == 100
    assert left.evidence.coverage_per_mille == 1000
