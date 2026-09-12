"""Read-only time evidence preview (H3/S7-1, O05)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Protocol

from travel_agent.application.common.errors import ResourceNotFoundError
from travel_agent.domain.admin import AdminPrincipal
from travel_agent.domain.place_catalog import HolidayCalendar

from .review_ports import TimeReviewUnitOfWork
from .review_support import ReviewSupport


class PreviewCalendarCatalog(Protocol):
    def list_calendars(self) -> tuple[HolidayCalendar, ...]: ...


class ReviewTimePreviewService(ReviewSupport):
    def __init__(
        self,
        uow_factory: Callable[[], TimeReviewUnitOfWork],
        holiday_calendars: PreviewCalendarCatalog,
    ) -> None:
        self._uow_factory = uow_factory
        self._holiday_calendars = holiday_calendars

    def preview_time(
        self, principal: AdminPrincipal, *, revision_id: str, service_date: date
    ) -> dict[str, object]:
        """Resolve one service date from verified O05 evidence without mutation."""
        self._require(principal, "place:candidate:read")
        with self._uow_factory() as uow:
            evidence = uow.catalog.load_revision_evidence(revision_id)
            if evidence is None:
                raise ResourceNotFoundError
        revision = evidence.revision

        def active(item: object) -> bool:
            return bool(
                item.active and item.review_status == "human_verified"  # type: ignore[attr-defined]
            )

        rules = tuple(
            sorted(
                (r for r in evidence.time_rules if active(r)),
                key=lambda r: (r.rule_kind, r.time_rule_id),
            )
        )
        closures = tuple(c for c in evidence.closures if active(c))
        exceptions = tuple(
            sorted(
                (
                    e
                    for e in evidence.date_exceptions
                    if active(e) and e.service_date == service_date
                ),
                key=lambda item: (
                    {"closed": 0, "session_override": 1, "open_override": 2}.get(
                        item.exception_kind, 9
                    ),
                    item.date_exception_id,
                ),
            )
        )
        calendars = self._holiday_calendars.list_calendars()
        holiday_open_dates = {day for calendar in calendars for day in calendar.holiday_dates()}
        holiday_shift_dates = {
            period.end + timedelta(days=1) for calendar in calendars for period in calendar.periods
        }
        reasons: list[str] = []
        sessions: list[dict[str, object]] = []
        if revision.is_always_open:
            reasons.append("PLACE_ALWAYS_OPEN")
            return {
                "revision_id": revision_id,
                "service_date": service_date.isoformat(),
                "open": True,
                "windows": [{"start_minute": 0, "end_minute": 1440, "last_entry_minute": None}],
                "fixed_sessions": [],
                "reason_codes": reasons,
                "applied_exception_ids": [],
                "rule_ids": [],
            }
        if len(exceptions) > 1:
            reasons.append("TIME_RULE_OVERLAP")
        if exceptions:
            exception = exceptions[0]
            if exception.exception_kind == "closed":
                reasons.append(
                    "HOLIDAY_CLOSURE_SHIFT"
                    if service_date in holiday_shift_dates
                    else "PLACE_DATE_EXCEPTION_CLOSED"
                )
                return {
                    "revision_id": revision_id,
                    "service_date": service_date.isoformat(),
                    "open": False,
                    "windows": [],
                    "fixed_sessions": [],
                    "reason_codes": reasons,
                    "applied_exception_ids": [e.date_exception_id for e in exceptions],
                    "rule_ids": [],
                }
            reasons.append(
                "HOLIDAY_OPEN_OVERRIDE"
                if service_date in holiday_open_dates
                else "PLACE_DATE_EXCEPTION_APPLIED"
            )
            if exception.start_minute is not None and exception.end_minute is not None:
                windows = [
                    {
                        "start_minute": exception.start_minute,
                        "end_minute": exception.end_minute,
                        "last_entry_minute": exception.last_entry_minute,
                    }
                ]
                if exception.exception_kind == "session_override":
                    sessions.append(
                        {
                            "date_exception_id": exception.date_exception_id,
                            "start_minute": exception.start_minute,
                            "end_minute": exception.end_minute,
                            "last_entry_minute": exception.last_entry_minute,
                        }
                    )
                if exception.end_minute > 1440:
                    reasons.append("CROSS_MIDNIGHT_WINDOW")
                return {
                    "revision_id": revision_id,
                    "service_date": service_date.isoformat(),
                    "open": True,
                    "windows": windows,
                    "fixed_sessions": sessions,
                    "reason_codes": reasons,
                    "applied_exception_ids": [e.date_exception_id for e in exceptions],
                    "rule_ids": [],
                }
        if any(c.weekday == service_date.isoweekday() for c in closures):
            reasons.append("PLACE_WEEKLY_CLOSED")
            return {
                "revision_id": revision_id,
                "service_date": service_date.isoformat(),
                "open": False,
                "windows": [],
                "fixed_sessions": [],
                "reason_codes": reasons,
                "applied_exception_ids": [],
                "rule_ids": [],
            }
        matching = tuple(
            r
            for r in rules
            if service_date.isoweekday() in r.weekdays
            and (r.valid_from is None or service_date >= r.valid_from)
            and (r.valid_to is None or service_date <= r.valid_to)
        )
        opening = tuple(r for r in matching if r.rule_kind == "opening_hours")
        fixed = tuple(r for r in matching if r.rule_kind == "fixed_session")
        last_entry = tuple(r for r in matching if r.rule_kind == "last_entry")
        if len(opening) > 1:
            reasons.append("TIME_RULE_OVERLAP")
        if not opening and fixed and evidence.revision.place_kind == "show":
            sessions = [
                {
                    "time_rule_id": item.time_rule_id,
                    "start_minute": item.start_minute,
                    "end_minute": item.end_minute,
                    "last_entry_minute": item.last_entry_minute,
                }
                for item in fixed
            ]
            if any((item.end_minute or 0) >= 1440 for item in fixed):
                reasons.append("CROSS_MIDNIGHT_WINDOW")
            return {
                "revision_id": revision_id,
                "service_date": service_date.isoformat(),
                "open": True,
                "windows": [],
                "fixed_sessions": sessions,
                "reason_codes": reasons,
                "applied_exception_ids": [],
                "rule_ids": [item.time_rule_id for item in fixed],
            }
        if not opening:
            reasons.append("TIME_RULE_NOT_MATCHED")
            return {
                "revision_id": revision_id,
                "service_date": service_date.isoformat(),
                "open": False,
                "windows": [],
                "fixed_sessions": [],
                "reason_codes": reasons,
                "applied_exception_ids": [],
                "rule_ids": [r.time_rule_id for r in matching],
            }
        rule = opening[0]
        end = rule.end_minute
        last = rule.last_entry_minute
        if last_entry and last_entry[0].last_entry_minute is not None:
            last = last_entry[0].last_entry_minute
        if end is None:
            end = 1440
        if last is not None and last > end:
            reasons.append("LAST_ENTRY_AFTER_CLOSE")
        if end > 1440 or (rule.start_minute or 0) >= 1440:
            reasons.append("CROSS_MIDNIGHT_WINDOW")
        for item in fixed:
            if item.start_minute is not None and item.end_minute is not None:
                sessions.append(
                    {
                        "time_rule_id": item.time_rule_id,
                        "start_minute": item.start_minute,
                        "end_minute": item.end_minute,
                        "last_entry_minute": item.last_entry_minute,
                    }
                )
        if (
            any(
                minute >= 1440
                for session in sessions
                for minute in (
                    session["start_minute"],
                    session["end_minute"],
                    session["last_entry_minute"],
                )
                if isinstance(minute, int)
            )
            and "CROSS_MIDNIGHT_WINDOW" not in reasons
        ):
            reasons.append("CROSS_MIDNIGHT_WINDOW")
        return {
            "revision_id": revision_id,
            "service_date": service_date.isoformat(),
            "open": True,
            "windows": [
                {"start_minute": rule.start_minute, "end_minute": end, "last_entry_minute": last}
            ],
            "fixed_sessions": sessions,
            "reason_codes": reasons,
            "applied_exception_ids": [],
            "rule_ids": [r.time_rule_id for r in matching],
        }
