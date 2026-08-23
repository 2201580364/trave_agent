"""Validation of raw attraction records before solver model construction.

Traceability: H3, ADR-0002, opening-time data specification rules 1-9, Gate 6.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import IntEnum
from typing import Any


ALLOWED_CATEGORIES = frozenset(
    {
        "自然山水",
        "古镇人文",
        "寺庙祈福",
        "城市观景",
        "博物馆",
        "美食街区",
        "网红打卡",
        "亲子乐园",
        "演出演艺",
    }
)


class DataRule(IntEnum):
    TIME_RULE_FIELDS = 1
    TIME_ORDER = 2
    LAST_ENTRY_AND_OVERLAP = 3
    CLOSE_DAYS = 4
    ALWAYS_OPEN_OR_MATCH = 5
    DURATION_ENERGY_CATEGORY = 6
    COORDINATES = 7
    PROVENANCE = 8
    SOLVER_ELIGIBILITY = 9


@dataclass(frozen=True, slots=True)
class GeoBounds:
    min_lat: float
    max_lat: float
    min_lng: float
    max_lng: float

    def __post_init__(self) -> None:
        if not -90 <= self.min_lat <= self.max_lat <= 90:
            raise ValueError("latitude bounds are invalid")
        if not -180 <= self.min_lng <= self.max_lng <= 180:
            raise ValueError("longitude bounds are invalid")

    def contains(self, lat: float, lng: float) -> bool:
        return self.min_lat <= lat <= self.max_lat and self.min_lng <= lng <= self.max_lng


@dataclass(frozen=True, slots=True)
class DataRuleResult:
    rule: DataRule
    passed: bool
    errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.passed == bool(self.errors):
            raise ValueError("data rule result is inconsistent")


@dataclass(frozen=True, slots=True)
class AttractionDataValidation:
    attraction_id: int | None
    rules: tuple[DataRuleResult, ...]
    structurally_valid: bool
    solver_eligible: bool

    def __post_init__(self) -> None:
        if tuple(item.rule for item in self.rules) != tuple(DataRule):
            raise ValueError("validation must contain each data rule exactly once")
        expected_structure = all(
            item.passed
            for item in self.rules
            if item.rule is not DataRule.SOLVER_ELIGIBILITY
        )
        if self.structurally_valid != expected_structure:
            raise ValueError("structural validation result is inconsistent")
        expected_eligibility = expected_structure and self.rules[-1].passed
        if self.solver_eligible != expected_eligibility:
            raise ValueError("solver eligibility result is inconsistent")


def validate_attraction_data(
    record: Mapping[str, Any],
    *,
    target_date: date | None = None,
    city_bounds: GeoBounds | None = None,
) -> AttractionDataValidation:
    """Evaluate all nine authoritative data rules without raising on bad input."""

    raw_rules = record.get("time_rules", ())
    time_rules = _mapping_sequence(raw_rules)
    parsed_rules, rule1_errors = _parse_time_rules(time_rules, raw_rules)
    rule2_errors = _time_order_errors(parsed_rules)
    rule3_errors = _last_entry_and_overlap_errors(parsed_rules)
    rule4_errors = _close_day_errors(record.get("close_days", ()))
    rule5_errors = _availability_shape_errors(record, parsed_rules, target_date)
    rule6_errors = _experience_field_errors(record)
    rule7_errors = _coordinate_errors(record, city_bounds)
    rule8_errors = _provenance_errors(record)
    rule9_errors = _eligibility_errors(record)
    errors_by_rule = (
        rule1_errors,
        rule2_errors,
        rule3_errors,
        rule4_errors,
        rule5_errors,
        rule6_errors,
        rule7_errors,
        rule8_errors,
        rule9_errors,
    )
    results = tuple(
        DataRuleResult(rule, not errors, tuple(errors))
        for rule, errors in zip(DataRule, errors_by_rule, strict=True)
    )
    structurally_valid = all(item.passed for item in results[:-1])
    return AttractionDataValidation(
        _optional_int(record.get("id")),
        results,
        structurally_valid,
        structurally_valid and results[-1].passed,
    )


@dataclass(frozen=True, slots=True)
class _ParsedTimeRule:
    start: tuple[int, int]
    end: tuple[int, int]
    open_min: int
    close_min: int
    last_entry_min: int | None
    crosses_midnight: bool


def _parse_time_rules(
    rules: tuple[Mapping[str, Any], ...],
    raw_rules: object,
) -> tuple[tuple[_ParsedTimeRule, ...], list[str]]:
    errors: list[str] = []
    parsed: list[_ParsedTimeRule] = []
    if not _is_sequence(raw_rules):
        return (), ["time_rules must be an array"]
    for index, rule in enumerate(rules):
        date_range = rule.get("date_range")
        if not _is_sequence(date_range) or len(date_range) != 2:
            errors.append(f"time_rules[{index}].date_range is invalid")
            continue
        try:
            start = _parse_month_day(date_range[0])
            end = _parse_month_day(date_range[1])
            open_min = _parse_clock(rule.get("open"))
            close_min = _parse_clock(rule.get("close"))
            last_entry = rule.get("last_entry")
            last_entry_min = _parse_clock(last_entry) if last_entry is not None else None
        except ValueError as exc:
            errors.append(f"time_rules[{index}]: {exc}")
            continue
        parsed.append(
            _ParsedTimeRule(
                start,
                end,
                open_min,
                close_min,
                last_entry_min,
                rule.get("crosses_midnight") is True,
            )
        )
    if len(rules) != len(parsed) and not errors:
        errors.append("one or more time rules are not objects")
    return tuple(parsed), errors


def _time_order_errors(rules: tuple[_ParsedTimeRule, ...]) -> list[str]:
    errors: list[str] = []
    for index, rule in enumerate(rules):
        if rule.crosses_midnight:
            if rule.close_min > rule.open_min:
                errors.append(
                    f"time_rules[{index}] crosses_midnight requires next-day close"
                )
        elif rule.close_min <= rule.open_min:
            errors.append(f"time_rules[{index}] close must be after open")
    return errors


def _last_entry_and_overlap_errors(rules: tuple[_ParsedTimeRule, ...]) -> list[str]:
    errors: list[str] = []
    occupied: set[int] = set()
    for index, rule in enumerate(rules):
        effective_close = rule.close_min
        effective_last_entry = rule.last_entry_min
        if rule.crosses_midnight:
            effective_close += 24 * 60
            if effective_last_entry is not None and effective_last_entry < rule.open_min:
                effective_last_entry += 24 * 60
        if effective_last_entry is not None:
            if effective_last_entry < rule.open_min:
                errors.append(f"time_rules[{index}] last_entry precedes open")
            elif effective_last_entry > effective_close:
                errors.append(f"time_rules[{index}] last_entry exceeds close")
        days = _date_range_days(rule.start, rule.end)
        if occupied.intersection(days):
            errors.append(f"time_rules[{index}] overlaps another date range")
        occupied.update(days)
    return errors


def _close_day_errors(value: object) -> list[str]:
    if not _is_sequence(value):
        return ["close_days must be an array"]
    days = tuple(value)
    if any(isinstance(day, bool) or not isinstance(day, int) for day in days):
        return ["close_days must contain integers"]
    errors: list[str] = []
    if len(set(days)) != len(days):
        errors.append("close_days must not contain duplicates")
    if any(day not in range(1, 8) for day in days):
        errors.append("close_days values must be within 1..7")
    return errors


def _availability_shape_errors(
    record: Mapping[str, Any],
    rules: tuple[_ParsedTimeRule, ...],
    target_date: date | None,
) -> list[str]:
    if record.get("is_always_open") is True:
        return []
    if not rules:
        return ["non-always-open attraction requires time_rules"]
    if target_date is not None:
        target_day = date(2000, target_date.month, target_date.day).timetuple().tm_yday
        if not any(target_day in _date_range_days(rule.start, rule.end) for rule in rules):
            return ["target_date does not match any time_rule"]
    return []


def _experience_field_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    duration = record.get("suggested_duration")
    if isinstance(duration, bool) or not isinstance(duration, int) or duration <= 0:
        errors.append("suggested_duration must be a positive integer")
    energy = record.get("energy_level")
    if isinstance(energy, bool) or not isinstance(energy, int) or energy not in range(1, 6):
        errors.append("energy_level must be within 1..5")
    if record.get("category") not in ALLOWED_CATEGORIES:
        errors.append("category is not in the nine-category enum")
    return errors


def _coordinate_errors(
    record: Mapping[str, Any],
    city_bounds: GeoBounds | None,
) -> list[str]:
    lat = record.get("lat")
    lng = record.get("lng")
    if not _is_number(lat) or not _is_number(lng):
        return ["lat and lng must be numbers"]
    lat_value = float(lat)
    lng_value = float(lng)
    errors: list[str] = []
    if not -90 <= lat_value <= 90 or not -180 <= lng_value <= 180:
        errors.append("coordinates exceed global ranges")
    elif city_bounds is not None and not city_bounds.contains(lat_value, lng_value):
        errors.append("coordinates fall outside target city bounds")
    return errors


def _provenance_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    source = record.get("data_source")
    if not isinstance(source, str) or not source.strip():
        errors.append("data_source is required")
    fetched_at = record.get("fetched_at")
    if not _valid_timestamp(fetched_at):
        errors.append("fetched_at must be a valid timezone-aware timestamp")
    if record.get("source_conflict_detected") is True and record.get("conflict") is not True:
        errors.append("detected source conflict must set conflict=true")
    return errors


def _eligibility_errors(record: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if record.get("data_verified") is not True:
        errors.append("data_verified must be true")
    if record.get("conflict") is True:
        errors.append("conflict must be false")
    return errors


def _mapping_sequence(value: object) -> tuple[Mapping[str, Any], ...]:
    if not _is_sequence(value):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _is_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _parse_month_day(value: object) -> tuple[int, int]:
    if not isinstance(value, str):
        raise ValueError("month-day must be a string")
    try:
        month, day = value.split("-", maxsplit=1)
        parsed = date(2000, int(month), int(day))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid month-day {value!r}") from exc
    return parsed.month, parsed.day


def _parse_clock(value: object) -> int:
    if not isinstance(value, str):
        raise ValueError("clock must be a string")
    try:
        hour, minute = (int(part) for part in value.split(":", maxsplit=1))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid clock {value!r}") from exc
    if hour == 24 and minute == 0:
        return 24 * 60
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid clock {value!r}")
    return hour * 60 + minute


def _date_range_days(start: tuple[int, int], end: tuple[int, int]) -> set[int]:
    start_day = date(2000, *start).timetuple().tm_yday
    end_day = date(2000, *end).timetuple().tm_yday
    if start_day <= end_day:
        return set(range(start_day, end_day + 1))
    return set(range(start_day, 367)).union(range(1, end_day + 1))


def _valid_timestamp(value: object) -> bool:
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return False
    else:
        return False
    return parsed.tzinfo is not None


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
