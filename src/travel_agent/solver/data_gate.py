"""P1 data-quality gate applied before any solver logic.

Traceability: H3, ADR-0002, data quality rules 8-9.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Attraction, RejectedAttraction, RejectionCode, SolverInputBatch


def filter_solver_inputs(attractions: Iterable[Attraction]) -> SolverInputBatch:
    """Allow only active, verified, conflict-free attractions into the solver.

    Rejection precedence is deterministic: inactive, unverified, then conflict.
    Every rejected attraction retains a machine-readable reason; nothing is
    silently dropped.
    """

    eligible: list[Attraction] = []
    rejected: list[RejectedAttraction] = []

    for attraction in attractions:
        if not attraction.active:
            rejected.append(RejectedAttraction(attraction, RejectionCode.INACTIVE))
        elif not attraction.data_verified:
            rejected.append(RejectedAttraction(attraction, RejectionCode.DATA_UNVERIFIED))
        elif attraction.conflict:
            rejected.append(RejectedAttraction(attraction, RejectionCode.DATA_CONFLICT))
        else:
            eligible.append(attraction)

    return SolverInputBatch(tuple(eligible), tuple(rejected))

