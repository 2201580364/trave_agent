"""Structured, side-effect-free degradation notices for itinerary output.

Traceability: H3, S6, Gate 6, ADR-0004, ADR-0006.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .models import ItineraryPlan, MealStatus
from .quality import SolverQualityReport


class DegradationCode(StrEnum):
    HIGH_ATTRACTION_COUNT = "HIGH_ATTRACTION_COUNT"
    UNPLACED_ATTRACTIONS = "UNPLACED_ATTRACTIONS"
    DINNER_UNSCHEDULED = "DINNER_UNSCHEDULED"


@dataclass(frozen=True, slots=True)
class DegradationNotice:
    code: DegradationCode
    message: str
    count: int
    recommended_per_day: int | None = None

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("degradation notice count must be positive")
        if self.recommended_per_day is not None and self.recommended_per_day <= 0:
            raise ValueError("recommended_per_day must be positive")


@dataclass(frozen=True, slots=True)
class DegradationReport:
    notices: tuple[DegradationNotice, ...]
    explainable: bool


def evaluate_itinerary_degradation(
    itinerary: ItineraryPlan,
    quality: SolverQualityReport,
    *,
    input_count: int,
    day_count: int,
    high_count_threshold: int = 25,
    recommended_per_day: int = 5,
) -> DegradationReport:
    """Explain safe fallback outcomes without changing the solved itinerary."""

    if input_count < 0:
        raise ValueError("input_count cannot be negative")
    if day_count <= 0:
        raise ValueError("day_count must be positive")
    if high_count_threshold <= 0 or recommended_per_day <= 0:
        raise ValueError("degradation thresholds must be positive")
    if quality.accounting.input_count != input_count:
        raise ValueError("input_count must match the quality report")

    notices: list[DegradationNotice] = []
    if input_count > high_count_threshold:
        notices.append(
            DegradationNotice(
                DegradationCode.HIGH_ATTRACTION_COUNT,
                (
                    f"已选择 {input_count} 个景点，建议每天不超过 "
                    f"{recommended_per_day} 个；系统将保留未排入原因"
                ),
                input_count,
                recommended_per_day,
            )
        )
    if itinerary.unplaced:
        notices.append(
            DegradationNotice(
                DegradationCode.UNPLACED_ATTRACTIONS,
                f"有 {len(itinerary.unplaced)} 个景点未排入，详情请查看原因列表",
                len(itinerary.unplaced),
            )
        )
    dinner_count = sum(
        item.meal_plan.status is MealStatus.UNSCHEDULED
        for item in itinerary.segmented_days
    )
    if dinner_count:
        notices.append(
            DegradationNotice(
                DegradationCode.DINNER_UNSCHEDULED,
                f"有 {dinner_count} 天晚餐时间紧张，请提前用餐或准备简餐",
                dinner_count,
            )
        )

    has_unplaced_notice = any(
        item.code is DegradationCode.UNPLACED_ATTRACTIONS for item in notices
    )
    has_dinner_notice = any(
        item.code is DegradationCode.DINNER_UNSCHEDULED for item in notices
    )
    explainable = (
        quality.gate_passed
        and bool(itinerary.unplaced) == has_unplaced_notice
        and bool(dinner_count) == has_dinner_notice
    )
    return DegradationReport(tuple(notices), explainable)
