"""Gate 7 research-environment lock tests. Traceability: Gate 7 R0.1."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from travel_agent.evaluation import (
    CURRENT_DATABASE_REVISION,
    LOCKED_PROTOCOL_SHA256,
    Gate7EvidenceError,
    GitState,
    build_gate7_environment_manifest,
    directory_sha256,
    environment_manifest_sha256,
    protocol_sha256,
    validate_evidence_environment_reference,
    validate_gate7_environment_manifest,
)
from travel_agent.evaluation.gate7 import load_json

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = ROOT / "docs" / "test" / "gate7-protocol-v1.json"


def _manifest(**overrides: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "protocol": load_json(PROTOCOL_PATH),
        "protocol_hash": protocol_sha256(PROTOCOL_PATH),
        "generated_at": datetime(2026, 8, 28, 9, tzinfo=UTC),
        "study_environment_id": "m1-hangzhou-formative-01",
        "study_phase": "formative",
        "git_state": GitState("a" * 40, True),
        "app_version": "0.1.0",
        "result_schema_version": "trip-result-v2",
        "solver_version": "solver-p1-v2",
        "constraint_version": "constraints-p1-v5",
        "parameter_version": "parameters-p1-2026-08-26",
        "data_snapshot_version": "hangzhou-published-2026-08-27-v1",
        "data_snapshot_kind": "published",
        "data_snapshot_sha256": "b" * 64,
        "city_id": "hangzhou",
        "database_revision": CURRENT_DATABASE_REVISION,
        "required_database_revision": CURRENT_DATABASE_REVISION,
        "frontend_build_kind": "h5-production",
        "frontend_build_sha256": "c" * 64,
        "evidence_storage_kind": "controlled_local",
        "limitations": [],
    }
    values.update(overrides)
    return build_gate7_environment_manifest(**values)


def test_reviewed_protocol_hash_is_stable() -> None:
    assert protocol_sha256(PROTOCOL_PATH) == LOCKED_PROTOCOL_SHA256


def test_clean_complete_environment_is_locked() -> None:
    manifest = _manifest()

    assert manifest["status"] == "locked"
    assert manifest["lock_reasons"] == []
    assert len(environment_manifest_sha256(manifest)) == 64


def test_dirty_tree_and_database_mismatch_cannot_lock() -> None:
    manifest = _manifest(
        git_state=GitState("a" * 40, False),
        database_revision="0002_anonymous_identity",
    )

    assert manifest["status"] == "candidate"
    assert manifest["lock_reasons"] == [
        "dirty_git_tree",
        "database_revision_mismatch",
    ]


def test_missing_frontend_artifact_cannot_lock() -> None:
    manifest = _manifest(frontend_build_sha256=None)

    assert manifest["status"] == "candidate"
    assert manifest["lock_reasons"] == ["frontend_artifact_missing"]


def test_protocol_hash_drift_is_rejected() -> None:
    with pytest.raises(Gate7EvidenceError, match="protocol hash drifted"):
        _manifest(protocol_hash="0" * 64)


def test_missing_critical_version_is_rejected() -> None:
    with pytest.raises(Gate7EvidenceError, match="app_version"):
        _manifest(app_version="")


def test_formal_study_cannot_mislabel_synthetic_data() -> None:
    manifest = _manifest(
        data_snapshot_kind="synthetic_fixture",
        data_snapshot_version="synthetic-do-not-publish",
    )

    assert manifest["status"] == "invalid"
    assert manifest["lock_reasons"] == ["formal_study_requires_published_data"]


def test_sensitive_or_unknown_manifest_content_is_rejected() -> None:
    manifest = _manifest()
    manifest["limitations"] = ["loaded from .env with password=example"]
    with pytest.raises(Gate7EvidenceError, match="sensitive text"):
        validate_gate7_environment_manifest(manifest)

    manifest = _manifest()
    manifest["database_url"] = "mysql://user:value@example.invalid/db"
    with pytest.raises(Gate7EvidenceError, match="fields mismatch"):
        validate_gate7_environment_manifest(manifest)

    manifest = _manifest()
    manifest["raw_evidence_in_git"] = True
    with pytest.raises(Gate7EvidenceError, match="must never be stored in Git"):
        validate_gate7_environment_manifest(manifest)


def test_directory_hash_is_stable_and_detects_content_changes(tmp_path: Path) -> None:
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("v1", encoding="utf-8")
    first = directory_sha256(build)
    assert first is not None
    assert first == directory_sha256(build)

    (build / "index.html").write_text("v2", encoding="utf-8")
    assert directory_sha256(build) != first


def test_real_evidence_must_reference_exact_locked_environment() -> None:
    manifest = _manifest()
    evidence = {
        "synthetic_fixture": False,
        "study_phase": "formative",
        "collection_started_at": "2026-09-01T09:00:00+08:00",
        "environment": {
            "study_environment_id": manifest["study_environment_id"],
            "environment_manifest_sha256": environment_manifest_sha256(manifest),
            **{
                key: manifest[key]
                for key in (
                    "app_version",
                    "result_schema_version",
                    "solver_version",
                    "constraint_version",
                    "parameter_version",
                    "data_snapshot_version",
                )
            },
        },
    }
    validate_evidence_environment_reference(evidence, manifest)

    changed = deepcopy(manifest)
    changed["parameter_version"] = "parameters-p1-drifted"
    with pytest.raises(Gate7EvidenceError, match="manifest sha256"):
        validate_evidence_environment_reference(evidence, changed)
