"""Decode the optional published fixed-session payload (H3/C2, ADR-0025)."""

from datetime import date
from typing import Any

from travel_agent.solver.models import FixedSession, TimeRule


def _day(value: object) -> date | None:
    return date.fromisoformat(str(value)) if value is not None else None


def _minute(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 2880:
        raise ValueError("invalid published session minute")
    return value


def _weekdays(value: object) -> frozenset[int]:
    if (
        not isinstance(value, list)
        or not value
        or any(type(v) is not int or not 1 <= v <= 7 for v in value)
    ):
        raise ValueError("invalid published session weekdays")
    return frozenset(value)


def _rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise ValueError("invalid published session records")
    return value


def _dates(value: object) -> frozenset[date]:
    if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
        raise ValueError("invalid published session excluded dates")
    return frozenset(date.fromisoformat(v) for v in value)


def _windows(payload: object) -> tuple[TimeRule, ...]:
    openings = []
    for r in _rows(payload):
        start, end = _minute(r.get("start_min")), _minute(r.get("end_min"))
        if start >= end:
            raise ValueError("invalid published opening hours")
        openings.append(
            TimeRule(
                1,
                1,
                12,
                31,
                start,
                end,
                _minute(r["last_entry_min"]) if r.get("last_entry_min") is not None else None,
                _weekdays(r.get("weekdays", list(range(1, 8)))),
                _day(r.get("valid_from")),
                _day(r.get("valid_to")),
                _dates(r.get("excluded_dates", [])),
            )
        )
    return tuple(openings)


def parse_fixed_sessions(payload: object) -> tuple[FixedSession, ...]:
    if not isinstance(payload, list):
        raise ValueError("fixed sessions must be an array")
    sessions = []
    for row in _rows(payload):
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("source_record_id"), str)
            or not row["source_record_id"]
        ):
            raise ValueError("fixed session must bind reviewed source evidence")
        if not isinstance(row.get("session_id"), str):
            raise ValueError("invalid published session id")
        sessions.append(
            FixedSession(
                row["session_id"],
                _minute(row.get("start_min")),
                _minute(row.get("end_min")),
                _minute(row["last_entry_min"]) if row.get("last_entry_min") is not None else None,
                _weekdays(row.get("weekdays", list(range(1, 8)))),
                _day(row.get("valid_from")),
                _day(row.get("valid_to")),
                _dates(row.get("excluded_dates", [])),
                _windows(row.get("opening_hours", [])),
                _windows(row.get("entry_deadlines", [])),
            )
        )
    if len({item.session_id for item in sessions}) != len(sessions):
        raise ValueError("duplicate published session id")
    return tuple(sessions)
