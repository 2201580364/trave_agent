"""C2/S1 tests. Traceability: H3, trip-solver S2, ADR-0002, ADR-0004."""

from datetime import date

import pytest

from travel_agent.solver import (
    Attraction,
    RejectionCode,
    TimeRule,
    evaluate_arrival,
    resolve_effective_window,
)


def _museum(*, last_entry: str | None = None) -> Attraction:
    return Attraction(
        1,
        "测试博物馆",
        suggested_duration=120,
        time_rules=(
            TimeRule.from_strings(("01-01", "12-31"), "09:00", "17:00", last_entry),
        ),
        data_verified=True,
    )


def test_c2_accepts_75_percent_visit_and_emits_duration_notice() -> None:
    evaluation = evaluate_arrival(_museum(), date(2026, 8, 26), arrival_min=15 * 60 + 30)

    assert evaluation.permitted
    assert evaluation.effective_arrival_min == 15 * 60 + 30
    assert evaluation.leave_min == 17 * 60
    assert evaluation.planned_duration_min == 90
    assert evaluation.duration_ratio == 0.75
    assert evaluation.duration_notice == "实际可玩 90 分钟（建议 120 分钟）"


def test_c2_rejects_arrival_below_60_percent_threshold() -> None:
    evaluation = evaluate_arrival(_museum(), date(2026, 8, 26), arrival_min=16 * 60 + 15)

    assert not evaluation.permitted
    assert evaluation.rejection_code is RejectionCode.ARRIVAL_AFTER_LATEST_ARRIVAL


def test_c2_allows_arrival_exactly_at_latest_boundary() -> None:
    # close 17:00 - ceil(120 * 0.6) = 15:48
    evaluation = evaluate_arrival(_museum(), date(2026, 8, 26), arrival_min=15 * 60 + 48)

    assert evaluation.permitted
    assert evaluation.planned_duration_min == 72
    assert evaluation.duration_ratio == 0.6


def test_c2_last_entry_can_be_stricter_than_duration_threshold() -> None:
    evaluation = evaluate_arrival(
        _museum(last_entry="15:30"),
        date(2026, 8, 26),
        arrival_min=15 * 60 + 31,
    )

    assert not evaluation.permitted
    assert evaluation.window is not None
    assert evaluation.window.latest_arrival_min == 15 * 60 + 30


def test_c2_waits_until_opening_time() -> None:
    evaluation = evaluate_arrival(_museum(), date(2026, 8, 26), arrival_min=8 * 60 + 30)

    assert evaluation.permitted
    assert evaluation.effective_arrival_min == 9 * 60
    assert evaluation.leave_min == 11 * 60
    assert evaluation.duration_notice is None


def test_c2_selects_seasonal_rule_for_visit_date() -> None:
    attraction = Attraction(
        1,
        "季节性景点",
        suggested_duration=120,
        time_rules=(
            TimeRule.from_strings(("01-01", "03-15"), "08:00", "17:30", "17:00"),
            TimeRule.from_strings(("03-16", "12-31"), "08:00", "19:00", "18:30"),
        ),
        data_verified=True,
    )

    resolution = resolve_effective_window(attraction, date(2026, 8, 26))

    assert resolution.window is not None
    assert resolution.window.close_min == 19 * 60
    assert resolution.window.last_entry_min == 18 * 60 + 30


def test_c2_supports_cross_year_date_range() -> None:
    attraction = Attraction(
        1,
        "冬季景点",
        time_rules=(TimeRule.from_strings(("11-01", "02-28"), "09:00", "17:00"),),
        data_verified=True,
    )

    assert resolve_effective_window(attraction, date(2026, 1, 10)).window is not None
    assert resolve_effective_window(attraction, date(2026, 7, 10)).rejection_code is (
        RejectionCode.NO_MATCHING_TIME_RULE
    )


def test_c2_returns_reason_when_no_time_rule_matches() -> None:
    attraction = Attraction(
        1,
        "暑期限定景点",
        time_rules=(TimeRule.from_strings(("07-01", "08-31"), "09:00", "17:00"),),
        data_verified=True,
    )

    resolution = resolve_effective_window(attraction, date(2026, 4, 1))

    assert resolution.window is None
    assert resolution.rejection_code is RejectionCode.NO_MATCHING_TIME_RULE


def test_c2_rejects_overlapping_matching_rules() -> None:
    attraction = Attraction(
        1,
        "冲突时间规则景点",
        time_rules=(
            TimeRule.from_strings(("01-01", "12-31"), "09:00", "17:00"),
            TimeRule.from_strings(("07-01", "08-31"), "10:00", "18:00"),
        ),
        data_verified=True,
    )

    resolution = resolve_effective_window(attraction, date(2026, 8, 1))

    assert resolution.window is None
    assert resolution.rejection_code is RejectionCode.TIME_RULE_CONFLICT


def test_c2_always_open_skips_time_rule_requirement() -> None:
    attraction = Attraction(
        1,
        "全天开放景点",
        suggested_duration=120,
        is_always_open=True,
        data_verified=True,
    )

    resolution = resolve_effective_window(attraction, date(2026, 8, 26))

    assert resolution.window is not None
    assert resolution.window.is_always_open
    assert resolution.window.open_min == 0
    assert resolution.window.close_min == 24 * 60


def test_c2_cross_midnight_rule_uses_next_day_minutes() -> None:
    rule = TimeRule.from_strings(
        ("01-01", "12-31"),
        "18:00",
        "01:00",
        "00:30",
        crosses_midnight=True,
    )

    assert rule.open_min == 18 * 60
    assert rule.close_min == 25 * 60
    assert rule.last_entry_min == 24 * 60 + 30


def test_c2_requires_explicit_cross_midnight_flag() -> None:
    with pytest.raises(ValueError, match="crosses_midnight"):
        TimeRule.from_strings(("01-01", "12-31"), "18:00", "01:00")


def test_c2_rejects_last_entry_after_close() -> None:
    with pytest.raises(ValueError, match="last_entry"):
        TimeRule.from_strings(("01-01", "12-31"), "09:00", "17:00", "18:00")

