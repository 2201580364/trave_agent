"""Build and validate non-sensitive Gate 7 research-environment manifests."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .gate7 import Gate7EvidenceError

MANIFEST_SCHEMA_VERSION = "gate7-research-environment-v1"
LOCKED_PROTOCOL_SHA256 = "b791f0558dfc93af4cc919ec6dd9b09d1251f8f1d54b7bc0bb8809eade742d89"
CURRENT_DATABASE_REVISION = "0013_backfill_solver_eligibility"

_FORMAL_PHASES = frozenset({"formative", "confirmatory", "field_pilot"})
_STUDY_PHASES = frozenset({"dry_run", *_FORMAL_PHASES})
_DATA_KINDS = frozenset({"published", "candidate", "synthetic_fixture"})
_STORAGE_KINDS = frozenset({"controlled_local", "controlled_external"})
_FRONTEND_BUILD_KINDS = frozenset({"h5-production", "weapp-production"})
_SOFT_LOCK_REASONS = frozenset(
    {
        "dirty_git_tree",
        "database_revision_mismatch",
        "frontend_artifact_missing",
    }
)
_INVALID_REASONS = frozenset({"formal_study_requires_published_data"})
_ALL_LOCK_REASONS = _SOFT_LOCK_REASONS | _INVALID_REASONS
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,159}")
_HEX_40 = re.compile(r"[0-9a-f]{40}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:\.env(?:\b|/|\\)|api[_ -]?key|password\s*[=:]|secret\s*[=:]|"
    r"access[_ -]?token|private[_ -]?key|-----BEGIN [A-Z ]*PRIVATE KEY-----|"
    r"[a-z][a-z0-9+.-]*://[^\s/:]+:[^\s/@]+@)"
)

_FIELDS = frozenset(
    {
        "manifest_schema_version",
        "study_environment_id",
        "status",
        "generated_at",
        "study_phase",
        "git_commit",
        "git_tree_clean",
        "protocol_id",
        "protocol_version",
        "protocol_sha256",
        "app_version",
        "result_schema_version",
        "solver_version",
        "constraint_version",
        "parameter_version",
        "data_snapshot_version",
        "data_snapshot_kind",
        "data_snapshot_sha256",
        "city_id",
        "database_revision",
        "required_database_revision",
        "frontend_build_kind",
        "frontend_build_sha256",
        "evidence_storage_kind",
        "raw_evidence_in_git",
        "lock_reasons",
        "limitations",
    }
)


@dataclass(frozen=True, slots=True)
class GitState:
    """Source revision and cleanliness observed before the manifest is written."""

    commit: str
    tree_clean: bool


def inspect_git_state(repository_root: Path) -> GitState:
    """Inspect Git without changing repository or global safe-directory settings."""

    root = repository_root.resolve()
    safe_root = root.as_posix()
    commit = _run_git(root, safe_root, "rev-parse", "HEAD").strip().lower()
    dirty = _run_git(
        root,
        safe_root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    )
    return GitState(commit=commit, tree_clean=not dirty.strip())


def directory_sha256(path: Path) -> str | None:
    """Hash a build directory deterministically, including relative file names."""

    if not path.is_dir():
        return None
    files = sorted(item for item in path.rglob("*") if item.is_file())
    if not files:
        return None
    digest = hashlib.sha256()
    for item in files:
        relative = item.relative_to(path).as_posix().encode("utf-8")
        payload = item.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def canonical_sha256(value: dict[str, Any]) -> str:
    """Hash JSON with the same cross-platform canonicalization as Gate 7 protocol."""

    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def environment_manifest_sha256(manifest: dict[str, Any]) -> str:
    validate_gate7_environment_manifest(manifest)
    return canonical_sha256(manifest)


def build_gate7_environment_manifest(
    *,
    protocol: dict[str, Any],
    protocol_hash: str,
    generated_at: datetime,
    study_environment_id: str,
    study_phase: str,
    git_state: GitState,
    app_version: str,
    result_schema_version: str,
    solver_version: str,
    constraint_version: str,
    parameter_version: str,
    data_snapshot_version: str,
    data_snapshot_kind: str,
    data_snapshot_sha256: str,
    city_id: str,
    database_revision: str,
    required_database_revision: str,
    frontend_build_kind: str,
    frontend_build_sha256: str | None,
    evidence_storage_kind: str,
    limitations: list[str],
) -> dict[str, Any]:
    """Build a manifest whose status is derived, never selected by the caller."""

    if generated_at.tzinfo is None:
        raise Gate7EvidenceError("environment generated_at must include a timezone")
    if protocol_hash != LOCKED_PROTOCOL_SHA256:
        raise Gate7EvidenceError("Gate 7 protocol hash drifted from the reviewed lock")

    lock_reasons: list[str] = []
    if not git_state.tree_clean:
        lock_reasons.append("dirty_git_tree")
    if database_revision != required_database_revision:
        lock_reasons.append("database_revision_mismatch")
    if frontend_build_sha256 is None:
        lock_reasons.append("frontend_artifact_missing")
    if study_phase in _FORMAL_PHASES and data_snapshot_kind != "published":
        lock_reasons.append("formal_study_requires_published_data")

    if any(reason in _INVALID_REASONS for reason in lock_reasons):
        status = "invalid"
    elif lock_reasons:
        status = "candidate"
    else:
        status = "locked"

    manifest: dict[str, Any] = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "study_environment_id": study_environment_id,
        "status": status,
        "generated_at": generated_at.isoformat(),
        "study_phase": study_phase,
        "git_commit": git_state.commit,
        "git_tree_clean": git_state.tree_clean,
        "protocol_id": protocol.get("protocol_id"),
        "protocol_version": protocol.get("protocol_version"),
        "protocol_sha256": protocol_hash,
        "app_version": app_version,
        "result_schema_version": result_schema_version,
        "solver_version": solver_version,
        "constraint_version": constraint_version,
        "parameter_version": parameter_version,
        "data_snapshot_version": data_snapshot_version,
        "data_snapshot_kind": data_snapshot_kind,
        "data_snapshot_sha256": data_snapshot_sha256,
        "city_id": city_id,
        "database_revision": database_revision,
        "required_database_revision": required_database_revision,
        "frontend_build_kind": frontend_build_kind,
        "frontend_build_sha256": frontend_build_sha256,
        "evidence_storage_kind": evidence_storage_kind,
        "raw_evidence_in_git": False,
        "lock_reasons": lock_reasons,
        "limitations": limitations,
    }
    validate_gate7_environment_manifest(manifest)
    return manifest


def validate_gate7_environment_manifest(manifest: dict[str, Any]) -> None:
    """Reject incomplete, self-contradictory, or potentially sensitive manifests."""

    unknown = set(manifest) - _FIELDS
    missing = _FIELDS - set(manifest)
    if missing or unknown:
        raise Gate7EvidenceError(
            f"environment manifest fields mismatch; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
    _reject_sensitive_text(manifest)

    _equal(manifest["manifest_schema_version"], MANIFEST_SCHEMA_VERSION, "manifest schema")
    _identifier(manifest, "study_environment_id")
    if manifest["status"] not in {"candidate", "locked", "invalid"}:
        raise Gate7EvidenceError("environment status is invalid")
    _aware_datetime(manifest["generated_at"], "environment generated_at")
    if manifest["study_phase"] not in _STUDY_PHASES:
        raise Gate7EvidenceError("environment study_phase is invalid")
    if not isinstance(manifest["git_tree_clean"], bool):
        raise Gate7EvidenceError("git_tree_clean must be boolean")
    if not isinstance(manifest["git_commit"], str) or _HEX_40.fullmatch(
        manifest["git_commit"]
    ) is None:
        raise Gate7EvidenceError("git_commit must be a full lowercase SHA-1")

    for key in (
        "protocol_id",
        "protocol_version",
        "app_version",
        "result_schema_version",
        "solver_version",
        "constraint_version",
        "parameter_version",
        "data_snapshot_version",
        "city_id",
        "database_revision",
        "required_database_revision",
    ):
        _identifier(manifest, key)
    for key in ("protocol_sha256", "data_snapshot_sha256"):
        _sha256(manifest, key, required=True)
    _sha256(manifest, "frontend_build_sha256", required=False)

    if manifest["protocol_sha256"] != LOCKED_PROTOCOL_SHA256:
        raise Gate7EvidenceError("environment protocol hash is not the reviewed lock")
    if manifest["data_snapshot_kind"] not in _DATA_KINDS:
        raise Gate7EvidenceError("data_snapshot_kind is invalid")
    if manifest["frontend_build_kind"] not in _FRONTEND_BUILD_KINDS:
        raise Gate7EvidenceError("frontend_build_kind is invalid")
    if manifest["evidence_storage_kind"] not in _STORAGE_KINDS:
        raise Gate7EvidenceError("evidence_storage_kind is invalid")
    if manifest["raw_evidence_in_git"] is not False:
        raise Gate7EvidenceError("raw Gate 7 evidence must never be stored in Git")

    reasons = manifest["lock_reasons"]
    if not isinstance(reasons, list) or any(reason not in _ALL_LOCK_REASONS for reason in reasons):
        raise Gate7EvidenceError("environment lock_reasons are invalid")
    if len(reasons) != len(set(reasons)):
        raise Gate7EvidenceError("environment lock_reasons must be unique")
    limitations = manifest["limitations"]
    if not isinstance(limitations, list) or not all(
        isinstance(item, str) and item.strip() for item in limitations
    ):
        raise Gate7EvidenceError("environment limitations must be non-empty strings")

    expected_reasons: set[str] = set()
    if not manifest["git_tree_clean"]:
        expected_reasons.add("dirty_git_tree")
    if manifest["database_revision"] != manifest["required_database_revision"]:
        expected_reasons.add("database_revision_mismatch")
    if manifest["frontend_build_sha256"] is None:
        expected_reasons.add("frontend_artifact_missing")
    if (
        manifest["study_phase"] in _FORMAL_PHASES
        and manifest["data_snapshot_kind"] != "published"
    ):
        expected_reasons.add("formal_study_requires_published_data")
    if set(reasons) != expected_reasons:
        raise Gate7EvidenceError("environment lock_reasons do not match manifest facts")

    expected_status = (
        "invalid"
        if expected_reasons & _INVALID_REASONS
        else "candidate"
        if expected_reasons
        else "locked"
    )
    if manifest["status"] != expected_status:
        raise Gate7EvidenceError("environment status does not match lock conditions")


def validate_evidence_environment_reference(
    evidence: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    """Bind evidence to one exact, pre-existing research environment."""

    validate_gate7_environment_manifest(manifest)
    environment = evidence.get("environment")
    if not isinstance(environment, dict):
        raise Gate7EvidenceError("environment must be an object")
    expected_hash = environment_manifest_sha256(manifest)
    _equal(
        environment.get("study_environment_id"),
        manifest["study_environment_id"],
        "study environment id",
    )
    _equal(
        environment.get("environment_manifest_sha256"),
        expected_hash,
        "environment manifest sha256",
    )
    _equal(evidence.get("study_phase"), manifest["study_phase"], "environment study phase")
    for key in (
        "app_version",
        "result_schema_version",
        "solver_version",
        "constraint_version",
        "parameter_version",
        "data_snapshot_version",
    ):
        _equal(environment.get(key), manifest[key], f"environment {key}")

    if evidence.get("synthetic_fixture") is not True and manifest["status"] != "locked":
        raise Gate7EvidenceError("real Gate 7 evidence requires a locked environment")
    started = _aware_datetime(evidence.get("collection_started_at"), "collection_started_at")
    generated = _aware_datetime(manifest["generated_at"], "environment generated_at")
    if generated > started:
        raise Gate7EvidenceError("environment must be locked before evidence collection starts")


def _run_git(root: Path, safe_root: str, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={safe_root}", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def _reject_sensitive_text(value: Any) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _SENSITIVE_TEXT.search(key):
                raise Gate7EvidenceError(f"sensitive environment manifest field: {key}")
            _reject_sensitive_text(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_sensitive_text(nested)
    elif isinstance(value, str) and _SENSITIVE_TEXT.search(value):
        raise Gate7EvidenceError("sensitive text is forbidden in environment manifests")


def _identifier(value: dict[str, Any], key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or _IDENTIFIER.fullmatch(result) is None:
        raise Gate7EvidenceError(f"{key} must be a safe non-empty identifier")
    return result


def _sha256(value: dict[str, Any], key: str, *, required: bool) -> None:
    result = value.get(key)
    if result is None and not required:
        return
    if not isinstance(result, str) or _HEX_64.fullmatch(result) is None:
        raise Gate7EvidenceError(f"{key} must be a lowercase SHA-256")


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


def _equal(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise Gate7EvidenceError(f"{field} does not match the locked environment")
