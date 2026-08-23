"""Nine-rule raw data validation. Traceability: H3, ADR-0002, data rules 1-9."""

from copy import deepcopy
from datetime import date

import pytest

from travel_agent.solver import DataRule, GeoBounds, validate_attraction_data


HANGZHOU_BOUNDS = GeoBounds(29.1, 30.6, 118.3, 120.8)


@pytest.fixture
def valid_record() -> dict[str, object]:
    return {
        "id": 1,
        "name": "灵隐寺",
        "category": "寺庙祈福",
        "energy_level": 4,
        "suggested_duration": 180,
        "is_indoor": False,
        "lat": 30.2409,
        "lng": 120.1022,
        "time_rules": [
            {
                "date_range": ["01-01", "12-31"],
                "open": "07:00",
                "close": "17:30",
                "last_entry": "16:30",
            }
        ],
        "is_always_open": False,
        "close_days": [],
        "data_source": "official",
        "fetched_at": "2026-08-23T09:00:00+08:00",
        "data_verified": True,
        "conflict": False,
    }


def _errors(record: dict[str, object], rule: DataRule) -> tuple[str, ...]:
    result = validate_attraction_data(
        record,
        target_date=date(2026, 8, 24),
        city_bounds=HANGZHOU_BOUNDS,
    )
    return result.rules[rule - 1].errors


def test_rule_1_requires_valid_time_rule_fields(valid_record: dict[str, object]) -> None:
    record = deepcopy(valid_record)
    record["time_rules"] = [{"date_range": ["02-30", "12-31"], "open": "bad"}]
    assert _errors(record, DataRule.TIME_RULE_FIELDS)


def test_rule_2_requires_explicit_cross_midnight(valid_record: dict[str, object]) -> None:
    record = deepcopy(valid_record)
    record["time_rules"] = [
        {"date_range": ["01-01", "12-31"], "open": "20:00", "close": "02:00"}
    ]
    assert _errors(record, DataRule.TIME_ORDER) == (
        "time_rules[0] close must be after open",
    )


def test_rule_3_rejects_last_entry_after_close_and_overlap(
    valid_record: dict[str, object],
) -> None:
    record = deepcopy(valid_record)
    record["time_rules"] = [
        {
            "date_range": ["01-01", "08-31"],
            "open": "09:00",
            "close": "17:00",
            "last_entry": "18:00",
        },
        {"date_range": ["08-01", "12-31"], "open": "09:00", "close": "18:00"},
    ]
    errors = _errors(record, DataRule.LAST_ENTRY_AND_OVERLAP)
    assert any("last_entry" in error for error in errors)
    assert any("overlaps" in error for error in errors)


def test_rule_4_rejects_duplicate_and_out_of_range_close_days(
    valid_record: dict[str, object],
) -> None:
    record = deepcopy(valid_record)
    record["close_days"] = [1, 1, 8]
    errors = _errors(record, DataRule.CLOSE_DAYS)
    assert len(errors) == 2


def test_rule_5_requires_rule_matching_target_date(valid_record: dict[str, object]) -> None:
    record = deepcopy(valid_record)
    record["time_rules"] = [
        {"date_range": ["01-01", "03-31"], "open": "09:00", "close": "17:00"}
    ]
    assert _errors(record, DataRule.ALWAYS_OPEN_OR_MATCH) == (
        "target_date does not match any time_rule",
    )
    record["is_always_open"] = True
    record["time_rules"] = []
    assert not _errors(record, DataRule.ALWAYS_OPEN_OR_MATCH)


def test_rule_6_validates_duration_energy_and_category(valid_record: dict[str, object]) -> None:
    record = deepcopy(valid_record)
    record.update(suggested_duration=0, energy_level=6, category="购物")
    assert len(_errors(record, DataRule.DURATION_ENERGY_CATEGORY)) == 3


def test_rule_7_validates_global_and_city_coordinates(valid_record: dict[str, object]) -> None:
    record = deepcopy(valid_record)
    record.update(lat=31.2304, lng=121.4737)
    assert _errors(record, DataRule.COORDINATES) == (
        "coordinates fall outside target city bounds",
    )


def test_rule_8_requires_provenance_and_marks_detected_conflict(
    valid_record: dict[str, object],
) -> None:
    record = deepcopy(valid_record)
    record.update(
        data_source="",
        fetched_at="not-a-time",
        source_conflict_detected=True,
        conflict=False,
    )
    assert len(_errors(record, DataRule.PROVENANCE)) == 3


def test_rule_9_only_allows_verified_conflict_free_records(
    valid_record: dict[str, object],
) -> None:
    valid = validate_attraction_data(valid_record, city_bounds=HANGZHOU_BOUNDS)
    assert valid.structurally_valid
    assert valid.solver_eligible

    record = deepcopy(valid_record)
    record.update(data_verified=False, conflict=True)
    invalid = validate_attraction_data(record, city_bounds=HANGZHOU_BOUNDS)
    assert invalid.structurally_valid
    assert not invalid.solver_eligible
    assert len(invalid.rules[DataRule.SOLVER_ELIGIBILITY - 1].errors) == 2
