"""C1 closed-day availability and deterministic cross-day reassignment.

Traceability: H3, trip-solver S1, C1, ADR-0002, ADR-0004.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date

from .models import Attraction, DateAssignment, RejectionCode


def is_open_on(attraction: Attraction, visit_date: date) -> bool:
    """Return whether C1 permits the attraction on ``visit_date``.

    Explicit one-off closure has highest precedence. An explicit opening date
    overrides the normal weekly closure. Otherwise ISO weekday membership in
    ``close_days`` decides availability.
    """

    if visit_date in attraction.closed_on_dates:
        return False
    if visit_date in attraction.open_on_dates:
        return True
    return visit_date.isoweekday() not in attraction.close_days


def assign_to_nearest_available_date(
    attraction: Attraction,
    preferred_date: date,
    trip_dates: Iterable[date],
) -> date | None:
    """Choose the nearest C1-valid trip date without silently dropping the POI.

    Ties are resolved toward the earlier date to keep output deterministic.
    ``None`` means every supplied trip date violates C1; the caller must expose
    ``NO_AVAILABLE_DATE`` in the unplaced output.
    """

    available_dates = {candidate for candidate in trip_dates if is_open_on(attraction, candidate)}
    if not available_dates:
        return None
    return min(
        available_dates,
        key=lambda candidate: (abs((candidate - preferred_date).days), candidate),
    )


def assign_attraction_date(
    attraction: Attraction,
    preferred_date: date,
    trip_dates: Iterable[date],
) -> DateAssignment:
    """Return either a C1-valid date or an explicit unplaced reason."""

    assigned_date = assign_to_nearest_available_date(attraction, preferred_date, trip_dates)
    if assigned_date is None:
        return DateAssignment(
            attraction=attraction,
            preferred_date=preferred_date,
            assigned_date=None,
            rejection_code=RejectionCode.NO_AVAILABLE_DATE,
        )
    return DateAssignment(
        attraction=attraction,
        preferred_date=preferred_date,
        assigned_date=assigned_date,
    )
