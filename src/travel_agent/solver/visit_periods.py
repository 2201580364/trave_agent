"""Soft visit-period preference evaluation, separate from C2 hard windows.

Traceability: H3, S3, ADR-0008.
"""

from __future__ import annotations

from .models import (
    TimeBucket,
    VisitPeriodEvaluation,
    VisitPeriodOutcome,
    VisitPeriodPreference,
    VisitPeriodPreferenceSource,
)


SOURCE_PRIORITY = {
    VisitPeriodPreferenceSource.PUBLIC_GUIDE_SYNTHESIS: 1,
    VisitPeriodPreferenceSource.CURATED: 2,
    VisitPeriodPreferenceSource.USER: 3,
}


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
    preferred_bucket = next(iter(preference.preferred_buckets))
    preferred_start, preferred_end = preferred_period_bounds(
        arrival_min,
        arrival_min,
        preferred_bucket,
    )
    deviation_min = max(
        preferred_start - arrival_min,
        arrival_min - preferred_end,
        0,
    )
    if actual in preference.preferred_buckets:
        outcome = VisitPeriodOutcome.PREFERRED
    elif actual in preference.acceptable_buckets:
        outcome = VisitPeriodOutcome.ACCEPTABLE
    else:
        outcome = VisitPeriodOutcome.FALLBACK
    return VisitPeriodEvaluation(
        preference,
        actual,
        outcome,
        deviation_min,
        _visit_period_notice(preference, actual, outcome),
    )


def preferred_period_bounds(
    earliest: int,
    latest: int,
    bucket: TimeBucket,
) -> tuple[int, int]:
    """Return the closest occurrence of a local-time bucket."""

    local_bounds = {
        TimeBucket.MORNING: (0, 12 * 60 - 1),
        TimeBucket.AFTERNOON: (12 * 60, 17 * 60 - 1),
        TimeBucket.EVENING: (17 * 60, 24 * 60 - 1),
    }[bucket]
    first_day = earliest // (24 * 60) - 1
    last_day = latest // (24 * 60) + 1
    candidates = tuple(
        (
            day_offset * 24 * 60 + local_bounds[0],
            day_offset * 24 * 60 + local_bounds[1],
        )
        for day_offset in range(first_day, last_day + 1)
    )

    def distance(interval: tuple[int, int]) -> tuple[int, int]:
        start, end = interval
        if end < earliest:
            gap = earliest - end
        elif start > latest:
            gap = start - latest
        else:
            gap = 0
        return gap, abs(start - earliest)

    return min(candidates, key=distance)


def _visit_period_notice(
    preference: VisitPeriodPreference,
    actual: TimeBucket,
    outcome: VisitPeriodOutcome,
) -> str:
    preferred = next(iter(preference.preferred_buckets)).value
    if outcome is VisitPeriodOutcome.PREFERRED:
        return f"已安排在优选的 {preferred} 时段"
    if outcome is VisitPeriodOutcome.ACCEPTABLE:
        return f"优选 {preferred} 时段；本次安排在可接受的 {actual.value} 时段"
    return (
        f"优选 {preferred} 时段；综合当前硬时间窗与路线衔接，"
        f"本次降级安排在 {actual.value} 时段"
    )


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
