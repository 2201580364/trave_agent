"""Data gate tests. Traceability: H3, ADR-0002, data rules 8-9."""

from travel_agent.solver import Attraction, RejectionCode, filter_solver_inputs


def test_only_verified_conflict_free_active_data_enters_solver() -> None:
    verified = Attraction(1, "已校准景点", data_verified=True)
    unverified = Attraction(2, "未校准景点")
    conflicted = Attraction(3, "冲突景点", data_verified=True, conflict=True)
    inactive = Attraction(4, "停用景点", data_verified=True, active=False)

    batch = filter_solver_inputs([verified, unverified, conflicted, inactive])

    assert batch.eligible == (verified,)
    assert [(item.attraction.id, item.code) for item in batch.rejected] == [
        (2, RejectionCode.DATA_UNVERIFIED),
        (3, RejectionCode.DATA_CONFLICT),
        (4, RejectionCode.INACTIVE),
    ]


def test_rejection_precedence_is_deterministic() -> None:
    inactive_unverified_conflict = Attraction(1, "多重问题", conflict=True, active=False)

    batch = filter_solver_inputs([inactive_unverified_conflict])

    assert batch.rejected[0].code is RejectionCode.INACTIVE

