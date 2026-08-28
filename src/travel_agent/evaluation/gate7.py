"""Validate anonymized Gate 7 evidence and build a non-identifying report."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

HYPOTHESIS_IDS = frozenset({"H1", "H2", "H3", "H6", "H7", "H11"})
ISSUE_STATUSES = frozenset({"open", "closed"})


class Gate7EvidenceError(ValueError):
    """Evidence is invalid or cannot be traced to the locked protocol."""


def protocol_sha256(path: Path) -> str:
    payload = load_json(path)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_gate7_evidence(
    protocol: dict[str, Any],
    evidence: dict[str, Any],
    *,
    expected_protocol_hash: str,
) -> None:
    _require_equal(protocol.get("schema_version"), "gate7-protocol-v1", "protocol schema")
    _require_equal(evidence.get("schema_version"), "gate7-evidence-v1", "evidence schema")
    _require_equal(
        evidence.get("protocol_id"),
        protocol.get("protocol_id"),
        "protocol id",
    )
    _require_equal(
        evidence.get("protocol_sha256"),
        expected_protocol_hash,
        "protocol sha256",
    )
    _reject_forbidden_fields(
        evidence,
        frozenset(protocol["repository_privacy"]["forbidden_field_names"]),
    )

    started = _aware_datetime(evidence.get("collection_started_at"), "collection_started_at")
    ended = _aware_datetime(evidence.get("collection_ended_at"), "collection_ended_at")
    created = _aware_datetime(protocol.get("created_at"), "protocol.created_at")
    if created > started:
        raise Gate7EvidenceError("protocol must be locked before evidence collection starts")
    if started > ended:
        raise Gate7EvidenceError("evidence collection end must not precede start")

    allowed_phases = set(protocol["scope"]["supported_study_phases"])
    phase = evidence.get("study_phase")
    if phase not in allowed_phases:
        raise Gate7EvidenceError("study_phase is not allowed by the protocol")
    if not isinstance(evidence.get("synthetic_fixture"), bool):
        raise Gate7EvidenceError("synthetic_fixture must be an explicit boolean")
    _required_string(evidence, "study_id")
    environment = evidence.get("environment")
    if not isinstance(environment, dict):
        raise Gate7EvidenceError("environment must be an object")
    for key in (
        "app_version",
        "result_schema_version",
        "solver_version",
        "constraint_version",
        "parameter_version",
        "data_snapshot_version",
    ):
        _required_string(environment, key)

    participants = _required_list(evidence, "participants")
    participant_ids: set[str] = set()
    participant_by_id: dict[str, dict[str, Any]] = {}
    allowed_roles = set(protocol["allowed_participant_roles"])
    for participant in participants:
        if not isinstance(participant, dict):
            raise Gate7EvidenceError("participant entries must be objects")
        participant_id = _required_string(participant, "participant_id")
        if participant_id in participant_ids:
            raise Gate7EvidenceError("participant ids must be unique")
        participant_ids.add(participant_id)
        participant_by_id[participant_id] = participant
        if participant.get("role") not in allowed_roles:
            raise Gate7EvidenceError("participant role is not allowed")
        if not isinstance(participant.get("eligible"), bool):
            raise Gate7EvidenceError("participant eligible must be a boolean")
        if (
            participant["eligible"]
            and participant.get("role") != "internal"
            and participant.get("consent_recorded") is not True
        ):
            raise Gate7EvidenceError("eligible external participants require consent")
        if not participant["eligible"] and not participant.get("exclusion_reason"):
            raise Gate7EvidenceError("excluded participants require an exclusion reason")

    observation_ids: set[str] = set()
    h3_participant_ids: set[str] = set()
    for observation in _required_list(evidence, "observations"):
        if not isinstance(observation, dict):
            raise Gate7EvidenceError("observation entries must be objects")
        observation_id = _required_string(observation, "observation_id")
        if observation_id in observation_ids:
            raise Gate7EvidenceError("observation ids must be unique")
        observation_ids.add(observation_id)
        participant_id = _required_string(observation, "participant_id")
        if participant_id not in participant_by_id:
            raise Gate7EvidenceError("observation references an unknown participant")
        if observation.get("hypothesis_id") not in HYPOTHESIS_IDS:
            raise Gate7EvidenceError("observation hypothesis_id is not a tracked M1 hypothesis")
        _required_string(observation, "metric")
        _required_string(observation, "scenario_id")
        _required_string(observation, "source_ref")
        recorded_at = _aware_datetime(
            observation.get("recorded_at"),
            "observation.recorded_at",
        )
        if recorded_at < started or recorded_at > ended:
            raise Gate7EvidenceError("observation timestamp is outside collection period")

        if observation["metric"] == "plan_preferred_over_manual":
            if observation.get("hypothesis_id") != "H3":
                raise Gate7EvidenceError("plan preference metric must belong to H3")
            participant = participant_by_id[participant_id]
            if participant.get("role") != "target_user":
                raise Gate7EvidenceError("H3 plan preference requires a target user")
            if not isinstance(observation.get("value"), bool):
                raise Gate7EvidenceError("H3 plan preference must be boolean")
            if participant_id in h3_participant_ids:
                raise Gate7EvidenceError("each participant may contribute one H3 primary outcome")
            h3_participant_ids.add(participant_id)

    allowed_severities = set(protocol["allowed_issue_severities"])
    allowed_attributions = set(protocol["allowed_attributions"])
    issue_ids: set[str] = set()
    for issue in _required_list(evidence, "issues"):
        if not isinstance(issue, dict):
            raise Gate7EvidenceError("issue entries must be objects")
        issue_id = _required_string(issue, "issue_id")
        if issue_id in issue_ids:
            raise Gate7EvidenceError("issue ids must be unique")
        issue_ids.add(issue_id)
        if issue.get("severity") not in allowed_severities:
            raise Gate7EvidenceError("issue severity is not allowed")
        if issue.get("status") not in ISSUE_STATUSES:
            raise Gate7EvidenceError("issue status is invalid")
        if issue.get("primary_attribution") not in allowed_attributions:
            raise Gate7EvidenceError("issue attribution is not allowed")
        secondary = issue.get("secondary_attribution")
        if secondary is not None and secondary not in allowed_attributions:
            raise Gate7EvidenceError("secondary issue attribution is not allowed")
        issue_participant_id = issue.get("participant_id")
        if (
            issue_participant_id is not None
            and issue_participant_id not in participant_by_id
        ):
            raise Gate7EvidenceError("issue references an unknown participant")
        _required_string(issue, "scenario_id")
        _required_string(issue, "source_ref")

    limitations = _required_list(evidence, "limitations")
    if not all(isinstance(item, str) and item.strip() for item in limitations):
        raise Gate7EvidenceError("limitations must contain non-empty strings")

    readiness = evidence.get("h11_readiness")
    if not isinstance(readiness, dict):
        raise Gate7EvidenceError("h11_readiness must be an object")
    for key in (
        "public_share_environment",
        "independent_recipients",
        "conversion_events",
    ):
        if not isinstance(readiness.get(key), bool):
            raise Gate7EvidenceError(f"h11_readiness.{key} must be boolean")


def build_gate7_report(
    protocol: dict[str, Any],
    evidence: dict[str, Any],
    *,
    expected_protocol_hash: str,
    generated_at: datetime,
) -> dict[str, Any]:
    validate_gate7_evidence(
        protocol,
        evidence,
        expected_protocol_hash=expected_protocol_hash,
    )
    if generated_at.tzinfo is None:
        raise Gate7EvidenceError("report timestamp must be timezone-aware")

    participants = evidence["participants"]
    eligible = [item for item in participants if item["eligible"]]
    role_counts = Counter(item["role"] for item in eligible)
    open_issues = [item for item in evidence["issues"] if item["status"] == "open"]
    issue_counts = Counter(item["severity"] for item in open_issues)

    h3_values = _eligible_h3_values(evidence, eligible)
    h3_rule = protocol["h3_decision_rule"]
    h3_rate = sum(h3_values) / len(h3_values) if h3_values else None
    h3_status = _h3_status(
        sample_size=len(h3_values),
        acceptance_rate=h3_rate,
        open_blockers=issue_counts["blocker"],
        synthetic_fixture=evidence["synthetic_fixture"],
        rule=h3_rule,
    )

    h11_ready = all(evidence["h11_readiness"].values())
    return {
        "schema_version": "gate7-aggregate-v1",
        "generated_at": generated_at.isoformat(),
        "protocol_id": protocol["protocol_id"],
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": expected_protocol_hash,
        "study_id": evidence["study_id"],
        "study_phase": evidence["study_phase"],
        "synthetic_fixture": evidence["synthetic_fixture"],
        "collection_started_at": evidence["collection_started_at"],
        "collection_ended_at": evidence["collection_ended_at"],
        "environment": dict(evidence["environment"]),
        "sample": {
            "recorded": len(participants),
            "eligible": len(eligible),
            "excluded": len(participants) - len(eligible),
            "eligible_by_role": dict(sorted(role_counts.items())),
        },
        "open_issues": {
            "total": len(open_issues),
            "by_severity": {
                severity: issue_counts[severity]
                for severity in protocol["allowed_issue_severities"]
            },
        },
        "hypotheses": {
            "H3": {
                "status": h3_status,
                "metric": h3_rule["metric"],
                "sample_size": len(h3_values),
                "accepted": sum(h3_values),
                "acceptance_rate": h3_rate,
                "minimum_sample_size": h3_rule["minimum_sample_size"],
                "supported_rate_gte": h3_rule["supported_rate_gte"],
                "refuted_rate_lt": h3_rule["refuted_rate_lt"],
                "open_blockers": issue_counts["blocker"],
            },
            "H11": {
                "status": "ready_for_collection" if h11_ready else "not_evaluable",
                "readiness": dict(evidence["h11_readiness"]),
                "note": (
                    "This report validates readiness only; share and conversion events "
                    "require a controlled public pilot."
                ),
            },
        },
        "gate7_overall_status": "not_decided_by_single_study",
        "limitations": list(evidence["limitations"]),
    }


def _eligible_h3_values(
    evidence: dict[str, Any],
    eligible_participants: list[dict[str, Any]],
) -> list[bool]:
    if evidence["study_phase"] != "confirmatory":
        return []
    eligible_ids = {
        item["participant_id"]
        for item in eligible_participants
        if item["role"] == "target_user"
    }
    return [
        observation["value"]
        for observation in evidence["observations"]
        if observation["participant_id"] in eligible_ids
        and observation["hypothesis_id"] == "H3"
        and observation["metric"] == "plan_preferred_over_manual"
    ]


def _h3_status(
    *,
    sample_size: int,
    acceptance_rate: float | None,
    open_blockers: int,
    synthetic_fixture: bool,
    rule: dict[str, Any],
) -> str:
    if synthetic_fixture:
        return "synthetic_only"
    if sample_size < rule["minimum_sample_size"]:
        return "insufficient_evidence"
    if acceptance_rate is None:
        return "insufficient_evidence"
    if acceptance_rate >= rule["supported_rate_gte"]:
        if rule["open_blocker_prevents_support"] and open_blockers:
            return "blocked_by_open_issue"
        return "supported"
    if acceptance_rate < rule["refuted_rate_lt"]:
        return "refuted"
    return "needs_adjustment"


def _reject_forbidden_fields(value: Any, forbidden: frozenset[str]) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key.lower() in forbidden:
                raise Gate7EvidenceError(f"forbidden repository field: {key}")
            _reject_forbidden_fields(nested, forbidden)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_fields(nested, forbidden)


def _required_list(value: dict[str, Any], key: str) -> list[Any]:
    result = value.get(key)
    if not isinstance(result, list):
        raise Gate7EvidenceError(f"{key} must be a list")
    return result


def _required_string(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise Gate7EvidenceError(f"{key} must be a non-empty string")
    return result


def _aware_datetime(value: Any, field: str) -> datetime:
    if not isinstance(value, str):
        raise Gate7EvidenceError(f"{field} must be an ISO datetime")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise Gate7EvidenceError(f"{field} must be an ISO datetime") from exc
    if parsed.tzinfo is None:
        raise Gate7EvidenceError(f"{field} must include a timezone")
    return parsed


def _require_equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise Gate7EvidenceError(f"{field} does not match the locked protocol")


def load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise Gate7EvidenceError("JSON root must be an object")
    return raw
