"""Gate 7 human-evidence validation tests. Traceability: H3, H11, Gate 7."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from travel_agent.evaluation import (
    Gate7EvidenceError,
    build_gate7_report,
    protocol_sha256,
    validate_gate7_evidence,
)
from travel_agent.evaluation.gate7 import load_json

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "docs" / "test" / "gate7-protocol-v1.json"


def _protocol() -> dict[str, Any]:
    return load_json(PROTOCOL_PATH)


def _evidence(*, sample_size: int = 21, accepted: int = 15) -> dict[str, Any]:
    participants = [
        {
            "participant_id": f"participant_{index:02d}",
            "role": "target_user",
            "cohort": "confirmatory",
            "eligible": True,
            "consent_recorded": True,
        }
        for index in range(sample_size)
    ]
    observations = [
        {
            "observation_id": f"observation_{index:02d}",
            "participant_id": participant["participant_id"],
            "hypothesis_id": "H3",
            "metric": "plan_preferred_over_manual",
            "value": index < accepted,
            "scenario_id": "hangzhou_personal_trip",
            "recorded_at": "2026-09-10T10:00:00+08:00",
            "source_ref": f"SOURCE-{index:02d}",
        }
        for index, participant in enumerate(participants)
    ]
    return {
        "schema_version": "gate7-evidence-v1",
        "study_id": "gate7-confirmatory-test",
        "protocol_id": "m1-hangzhou-gate7-v1",
        "protocol_sha256": protocol_sha256(PROTOCOL_PATH),
        "synthetic_fixture": False,
        "study_phase": "confirmatory",
        "collection_started_at": "2026-09-01T09:00:00+08:00",
        "collection_ended_at": "2026-09-20T18:00:00+08:00",
        "environment": {
            "app_version": "0.1.0-test",
            "result_schema_version": "trip-result-v2",
            "solver_version": "solver-p1-v2",
            "constraint_version": "constraints-p1-v5",
            "parameter_version": "parameters-p1-2026-08-26",
            "data_snapshot_version": "hangzhou-test-v1",
        },
        "participants": participants,
        "observations": observations,
        "issues": [],
        "h11_readiness": {
            "public_share_environment": False,
            "independent_recipients": False,
            "conversion_events": False,
        },
        "limitations": ["Synthetic test object; not real Gate 7 evidence."],
    }


def _report(evidence: dict[str, Any]) -> dict[str, Any]:
    return build_gate7_report(
        _protocol(),
        evidence,
        expected_protocol_hash=protocol_sha256(PROTOCOL_PATH),
        generated_at=datetime(2026, 9, 21, tzinfo=UTC),
    )


def test_h3_support_requires_twenty_one_users_and_seventy_percent() -> None:
    report = _report(_evidence(sample_size=21, accepted=15))

    assert report["hypotheses"]["H3"]["status"] == "supported"
    assert report["hypotheses"]["H3"]["sample_size"] == 21
    assert report["hypotheses"]["H3"]["acceptance_rate"] == pytest.approx(15 / 21)
    assert report["hypotheses"]["H11"]["status"] == "not_evaluable"
    assert report["gate7_overall_status"] == "not_decided_by_single_study"


@pytest.mark.parametrize(
    ("sample_size", "accepted", "expected"),
    (
        (20, 20, "insufficient_evidence"),
        (21, 10, "refuted"),
        (21, 12, "needs_adjustment"),
    ),
)
def test_h3_decision_has_explicit_insufficient_and_middle_states(
    sample_size: int,
    accepted: int,
    expected: str,
) -> None:
    assert _report(_evidence(sample_size=sample_size, accepted=accepted))["hypotheses"][
        "H3"
    ]["status"] == expected


def test_open_blocker_prevents_h3_support() -> None:
    evidence = _evidence()
    evidence["issues"].append(
        {
            "issue_id": "issue_blocker_1",
            "severity": "blocker",
            "status": "open",
            "primary_attribution": "data",
            "secondary_attribution": None,
            "participant_id": "participant_00",
            "scenario_id": "hangzhou_personal_trip",
            "source_ref": "SOURCE-BLOCKER-1",
        }
    )

    assert _report(evidence)["hypotheses"]["H3"]["status"] == "blocked_by_open_issue"


def test_synthetic_fixture_can_never_support_h3() -> None:
    evidence = _evidence()
    evidence["synthetic_fixture"] = True

    assert _report(evidence)["hypotheses"]["H3"]["status"] == "synthetic_only"


def test_internal_or_excluded_participants_do_not_enter_h3_denominator() -> None:
    evidence = _evidence()
    evidence["participants"][0]["eligible"] = False
    evidence["participants"][0]["exclusion_reason"] = "duplicate household"

    report = _report(evidence)

    assert report["hypotheses"]["H3"]["sample_size"] == 20
    assert report["hypotheses"]["H3"]["status"] == "insufficient_evidence"


def test_protocol_hash_drift_and_personal_fields_are_rejected() -> None:
    evidence = _evidence()
    evidence["protocol_sha256"] = "0" * 64
    with pytest.raises(Gate7EvidenceError, match="protocol sha256"):
        validate_gate7_evidence(
            _protocol(),
            evidence,
            expected_protocol_hash=protocol_sha256(PROTOCOL_PATH),
        )

    evidence = _evidence()
    evidence["participants"][0]["email"] = "not-allowed@example.test"
    with pytest.raises(Gate7EvidenceError, match="forbidden repository field"):
        validate_gate7_evidence(
            _protocol(),
            evidence,
            expected_protocol_hash=protocol_sha256(PROTOCOL_PATH),
        )


def test_duplicate_primary_outcome_and_missing_consent_are_rejected() -> None:
    evidence = _evidence()
    duplicate = deepcopy(evidence["observations"][0])
    duplicate["observation_id"] = "duplicate_observation"
    evidence["observations"].append(duplicate)
    with pytest.raises(Gate7EvidenceError, match="one H3 primary outcome"):
        _report(evidence)

    evidence = _evidence()
    evidence["participants"][0]["consent_recorded"] = False
    with pytest.raises(Gate7EvidenceError, match="require consent"):
        _report(evidence)
