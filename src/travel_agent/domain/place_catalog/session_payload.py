"""Publish discrete, reviewed show sessions without broadening time windows (H3/C2)."""

from .evidence import PlaceRevisionEvidence


def build_fixed_session_payload(evidence: PlaceRevisionEvidence) -> list[dict[str, object]]:
    sources = {s.source_record_id for s in evidence.source_records if s.status == "active"}
    rules = [
        r
        for r in evidence.time_rules
        if r.active and r.review_status == "human_verified" and r.source_record_id in sources
    ]
    exceptions = [
        e
        for e in evidence.date_exceptions
        if e.active and e.review_status == "human_verified" and e.source_record_id in sources
    ]
    session_overrides = [e for e in exceptions if e.exception_kind == "session_override"]
    open_overrides = [e for e in exceptions if e.exception_kind == "open_override"]
    excluded = sorted(e.service_date.isoformat() for e in session_overrides)
    openings: list[dict[str, object]] = [
        {
            "start_min": r.start_minute if r.start_minute is not None else 0,
            "end_min": r.end_minute if r.end_minute is not None else 1440,
            "last_entry_min": r.last_entry_minute,
            "weekdays": sorted(r.weekdays),
            "valid_from": r.valid_from.isoformat() if r.valid_from else None,
            "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            "excluded_dates": sorted(e.service_date.isoformat() for e in open_overrides),
        }
        for r in rules
        if r.rule_kind == "opening_hours"
    ]
    openings.extend(
        {
            "start_min": e.start_minute,
            "end_min": e.end_minute,
            "last_entry_min": e.last_entry_minute,
            "weekdays": list(range(1, 8)),
            "valid_from": e.service_date.isoformat(),
            "valid_to": e.service_date.isoformat(),
            "excluded_dates": [],
        }
        for e in open_overrides
    )
    entry_deadlines: list[dict[str, object]] = [
        {
            "start_min": 0,
            "end_min": 2880,
            "last_entry_min": r.last_entry_minute,
            "weekdays": sorted(r.weekdays),
            "valid_from": r.valid_from.isoformat() if r.valid_from else None,
            "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            "excluded_dates": sorted(e.service_date.isoformat() for e in open_overrides),
        }
        for r in rules
        if r.rule_kind == "last_entry" and r.last_entry_minute is not None
    ]
    result: list[dict[str, object]] = [
        {
            "session_id": r.time_rule_id,
            "source_record_id": r.source_record_id,
            "start_min": r.start_minute,
            "end_min": r.end_minute,
            "last_entry_min": r.last_entry_minute,
            "weekdays": sorted(r.weekdays),
            "valid_from": r.valid_from.isoformat() if r.valid_from else None,
            "valid_to": r.valid_to.isoformat() if r.valid_to else None,
            "excluded_dates": excluded,
            "opening_hours": openings,
            "entry_deadlines": entry_deadlines,
        }
        for r in rules
        if r.rule_kind == "fixed_session"
    ]
    result.extend(
        {
            "session_id": e.date_exception_id,
            "source_record_id": e.source_record_id,
            "start_min": e.start_minute,
            "end_min": e.end_minute,
            "last_entry_min": e.last_entry_minute,
            "weekdays": list(range(1, 8)),
            "valid_from": e.service_date.isoformat(),
            "valid_to": e.service_date.isoformat(),
            "excluded_dates": [],
            "opening_hours": [],
        }
        for e in session_overrides
    )
    return sorted(result, key=lambda item: str(item["session_id"]))


def valid_session_timing(start: int | None, end: int | None, entry: int | None) -> bool:
    """H3/C2: incomplete candidates remain editable but cannot pass readiness."""
    return (
        start is not None and end is not None and start < end and (entry is None or entry <= start)
    )
