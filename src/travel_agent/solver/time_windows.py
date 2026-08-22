"""C2 effective time-window resolution and S1 duration annotation.

Traceability: H3, trip-solver S2, C2, S1, ADR-0002, ADR-0004.
"""

from __future__ import annotations

import math
from datetime import date

from .models import (
    ArrivalEvaluation,
    Attraction,
    EffectiveTimeWindow,
    RejectionCode,
    TimeWindowResolution,
)

DEFAULT_DURATION_RATIO = 0.6
MINUTES_PER_DAY = 24 * 60


def resolve_effective_window(
    attraction: Attraction,
    visit_date: date,
    *,
    duration_ratio: float = DEFAULT_DURATION_RATIO,
) -> TimeWindowResolution:
    """Resolve the single C2 window applicable to ``visit_date``."""

    if not 0 < duration_ratio <= 1:
        raise ValueError("duration_ratio must be within (0, 1]")

    required_duration = math.ceil(attraction.suggested_duration * duration_ratio)
    if attraction.is_always_open:
        return TimeWindowResolution(
            window=EffectiveTimeWindow(
                open_min=0,
                close_min=MINUTES_PER_DAY,
                last_entry_min=None,
                latest_arrival_min=MINUTES_PER_DAY - required_duration,
                is_always_open=True,
            )
        )

    matching_rules = [rule for rule in attraction.time_rules if rule.matches(visit_date)]
    if not matching_rules:
        return TimeWindowResolution(None, RejectionCode.NO_MATCHING_TIME_RULE)
    if len(matching_rules) > 1:
        return TimeWindowResolution(None, RejectionCode.TIME_RULE_CONFLICT)

    rule = matching_rules[0]
    duration_latest = rule.close_min - required_duration
    latest_arrival = min(
        rule.last_entry_min if rule.last_entry_min is not None else rule.close_min,
        duration_latest,
    )
    return TimeWindowResolution(
        window=EffectiveTimeWindow(
            open_min=rule.open_min,
            close_min=rule.close_min,
            last_entry_min=rule.last_entry_min,
            latest_arrival_min=latest_arrival,
        )
    )


def evaluate_arrival(
    attraction: Attraction,
    visit_date: date,
    arrival_min: int,
    *,
    duration_ratio: float = DEFAULT_DURATION_RATIO,
) -> ArrivalEvaluation:
    """Evaluate one arrival against C2 and produce the deterministic S1 notice."""

    resolution = resolve_effective_window(
        attraction,
        visit_date,
        duration_ratio=duration_ratio,
    )
    if resolution.window is None:
        return ArrivalEvaluation(
            permitted=False,
            window=None,
            rejection_code=resolution.rejection_code,
        )

    window = resolution.window
    effective_arrival = max(arrival_min, window.open_min)
    if effective_arrival > window.latest_arrival_min:
        return ArrivalEvaluation(
            permitted=False,
            window=window,
            effective_arrival_min=effective_arrival,
            rejection_code=RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL,
        )

    playable_duration = min(
        attraction.suggested_duration,
        window.close_min - effective_arrival,
    )
    actual_ratio = playable_duration / attraction.suggested_duration
    notice = None
    if playable_duration < attraction.suggested_duration:
        notice = (
            f"实际可玩 {playable_duration} 分钟"
            f"（建议 {attraction.suggested_duration} 分钟）"
        )

    return ArrivalEvaluation(
        permitted=True,
        window=window,
        effective_arrival_min=effective_arrival,
        leave_min=effective_arrival + playable_duration,
        planned_duration_min=playable_duration,
        duration_ratio=actual_ratio,
        duration_notice=notice,
    )

