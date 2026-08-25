"""P1 solver contract freeze tests. Traceability: H3, Gate 6, ADR-0009."""

from travel_agent.solver import (
    CONSTRAINT_VERSION,
    DEFAULT_SOLVER_P1_CONTRACT,
    PARAMETER_VERSION,
    SOLVER_CONTRACT_VERSION,
)


def test_p1_contract_versions_and_parameters_are_frozen() -> None:
    contract = DEFAULT_SOLVER_P1_CONTRACT

    assert contract.contract_version == SOLVER_CONTRACT_VERSION == "solver-p1-v1"
    assert contract.constraint_version == CONSTRAINT_VERSION == "constraints-p1-v2"
    assert contract.parameter_version == PARAMETER_VERSION == "parameters-p1-2026-08-25"
    assert dict(contract.duration_ratios) == {
        "speed": 0.6,
        "normal": 0.6,
        "leisure": 0.7,
    }
    assert contract.transit_buffer_ratio == 1.2
    assert contract.route_time_limit_seconds == 2
    assert contract.drop_penalty == 1_000_000
    assert contract.travel_cost_scale == 30
    assert contract.period_deviation_cost == 1
    assert contract.day_spread_target_end_min == 16 * 60
    assert contract.day_spread_max_delay_min == 60
    assert contract.lunch_earliest_min == 11 * 60 + 30
    assert contract.lunch_latest_end_min == 14 * 60
    assert contract.lunch_duration_min == 60
    assert contract.dinner_full_duration_min == 90
    assert contract.dinner_reduced_duration_min == 60


def test_p1_contract_freezes_public_constraint_and_status_vocabulary() -> None:
    contract = DEFAULT_SOLVER_P1_CONTRACT

    assert contract.hard_constraints == ("C1", "C2", "C4", "C5", "C6")
    assert contract.time_buckets == (
        ("morning", 0, 719),
        ("afternoon", 720, 1019),
        ("evening", 1020, 1439),
    )
    assert contract.search_statuses == (
        "empty",
        "completed",
        "best_so_far",
        "time_limit_no_solution",
        "no_solution",
        "invalid",
    )
    assert "CLOSED_ON_DATE" in contract.rejection_codes
    assert "SOLVER_TIME_LIMIT" in contract.rejection_codes
    assert "TRANSIT_INFEASIBLE" in contract.rejection_codes
    assert "LUNCH_BLOCK" in contract.soft_objectives
    assert "DAY_SPREAD" in contract.soft_objectives


def test_p1_contract_is_machine_serializable() -> None:
    payload = DEFAULT_SOLVER_P1_CONTRACT.to_dict()

    assert payload["contract_version"] == "solver-p1-v1"
    assert payload["hard_constraints"] == ("C1", "C2", "C4", "C5", "C6")
    assert payload["rejection_codes"]
