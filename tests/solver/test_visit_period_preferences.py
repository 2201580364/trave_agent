"""Soft visit-period preference model tests. Traceability: H3, S3, ADR-0008."""

from datetime import date

import pytest

from travel_agent.solver import (
    Attraction,
    AttractionPreference,
    TimeBucket,
    VisitPeriodOutcome,
    VisitPeriodPreference,
    VisitPeriodPreferenceSource,
    evaluate_visit_period,
    resolve_visit_period_preference,
    time_bucket_for,
)


def _preference() -> VisitPeriodPreference:
    return VisitPeriodPreference(
        frozenset({TimeBucket.EVENING}),
        frozenset({TimeBucket.AFTERNOON}),
        VisitPeriodPreferenceSource.PUBLIC_GUIDE_SYNTHESIS,
        "SRC-HEFANG-STREET-GUIDE",
    )


@pytest.mark.parametrize(
    ("arrival_min", "bucket"),
    (
        (0, TimeBucket.MORNING),
        (11 * 60 + 59, TimeBucket.MORNING),
        (12 * 60, TimeBucket.AFTERNOON),
        (16 * 60 + 59, TimeBucket.AFTERNOON),
        (17 * 60, TimeBucket.EVENING),
        (25 * 60, TimeBucket.MORNING),
    ),
)
def test_time_bucket_boundaries(arrival_min: int, bucket: TimeBucket) -> None:
    assert time_bucket_for(arrival_min) is bucket


def test_visit_period_evaluation_distinguishes_three_soft_outcomes() -> None:
    preference = _preference()

    assert evaluate_visit_period(18 * 60, preference).outcome is VisitPeriodOutcome.PREFERRED
    assert evaluate_visit_period(15 * 60, preference).outcome is VisitPeriodOutcome.ACCEPTABLE
    assert evaluate_visit_period(10 * 60, preference).outcome is VisitPeriodOutcome.FALLBACK


def test_visit_period_preference_requires_disjoint_buckets_and_source() -> None:
    with pytest.raises(ValueError, match="one preferred bucket"):
        VisitPeriodPreference(
            frozenset({TimeBucket.MORNING, TimeBucket.EVENING}),
            source_ref="SRC-1",
        )
    with pytest.raises(ValueError, match="must not overlap"):
        VisitPeriodPreference(
            frozenset({TimeBucket.EVENING}),
            frozenset({TimeBucket.EVENING}),
            source_ref="SRC-1",
        )
    with pytest.raises(ValueError, match="source reference"):
        VisitPeriodPreference(frozenset({TimeBucket.EVENING}))


def test_attraction_preference_carries_soft_period_without_changing_attraction() -> None:
    attraction = Attraction(1, "河坊街", data_verified=True)
    preference = AttractionPreference(attraction, date(2026, 8, 26), _preference())

    assert preference.visit_period is not None
    assert preference.attraction.time_rules == ()


def test_user_preference_overrides_curated_and_public_guide_sources() -> None:
    public = _preference()
    curated = VisitPeriodPreference(
        frozenset({TimeBucket.AFTERNOON}),
        source=VisitPeriodPreferenceSource.CURATED,
        source_ref="CURATOR-1",
    )
    user = VisitPeriodPreference(
        frozenset({TimeBucket.MORNING}),
        source=VisitPeriodPreferenceSource.USER,
        source_ref="TRIP-REQUEST-1",
    )

    assert resolve_visit_period_preference((public, curated, user)) is user


def test_same_level_conflict_is_rejected_instead_of_silently_selected() -> None:
    first = VisitPeriodPreference(
        frozenset({TimeBucket.MORNING}),
        source_ref="CURATOR-1",
    )
    second = VisitPeriodPreference(
        frozenset({TimeBucket.EVENING}),
        source_ref="CURATOR-2",
    )

    with pytest.raises(ValueError, match="same source level"):
        resolve_visit_period_preference((first, second))
