"""Soft visit-period preference evaluation, separate from C2 hard windows.

Traceability: H3, S3, ADR-0008.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import (
    TimeBucket,
    VisitPeriodOutcome,
    VisitPeriodPreference,
    VisitPeriodPreferenceSource,
)


SOURCE_PRIORITY = {
    VisitPeriodPreferenceSource.PUBLIC_GUIDE_SYNTHESIS: 1,
    VisitPeriodPreferenceSource.CURATED: 2,
    VisitPeriodPreferenceSource.USER: 3,
}


@dataclass(frozen=True, slots=True)
class VisitPeriodEvaluation:
    actual_bucket: TimeBucket
    outcome: VisitPeriodOutcome


def time_bucket_for(arrival_min: int) -> TimeBucket:
    """Map an arrival minute to the stable morning/afternoon/evening buckets."""

    if arrival_min < 0:
        raise ValueError("arrival_min must be non-negative")
    local_minute = arrival_min % (24 * 60)
    if local_minute < 12 * 60:
        return TimeBucket.MORNING
    if local_minute < 17 * 60:
        return TimeBucket.AFTERNOON
    return TimeBucket.EVENING


def evaluate_visit_period(
    arrival_min: int,
    preference: VisitPeriodPreference,
) -> VisitPeriodEvaluation:
    """Classify a hard-feasible arrival without making the preference a constraint."""

    actual = time_bucket_for(arrival_min)
    if actual in preference.preferred_buckets:
        outcome = VisitPeriodOutcome.PREFERRED
    elif actual in preference.acceptable_buckets:
        outcome = VisitPeriodOutcome.ACCEPTABLE
    else:
        outcome = VisitPeriodOutcome.FALLBACK
    return VisitPeriodEvaluation(actual, outcome)


def resolve_visit_period_preference(
    preferences: tuple[VisitPeriodPreference, ...],
) -> VisitPeriodPreference | None:
    """Select the strongest declared source and reject same-level conflicts."""

    if not preferences:
        return None
    highest_priority = max(SOURCE_PRIORITY[item.source] for item in preferences)
    strongest = tuple(
        item
        for item in preferences
        if SOURCE_PRIORITY[item.source] == highest_priority
    )
    distinct = {
        (item.preferred_buckets, item.acceptable_buckets)
        for item in strongest
    }
    if len(distinct) > 1:
        raise ValueError("conflicting visit-period preferences at the same source level")
    return sorted(strongest, key=lambda item: item.source_ref)[0]
