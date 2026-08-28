"""Create a non-sensitive Gate 7 research-environment manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tomllib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.evaluation import (  # noqa: E402
    CURRENT_DATABASE_REVISION,
    build_gate7_environment_manifest,
    directory_sha256,
    environment_manifest_sha256,
    inspect_git_state,
    protocol_sha256,
)
from travel_agent.evaluation.gate7 import load_json  # noqa: E402
from travel_agent.infrastructure.solver.published_json import (  # noqa: E402
    JsonPublishedSolverDataProvider,
)
from travel_agent.solver import (  # noqa: E402
    CONSTRAINT_VERSION,
    PARAMETER_VERSION,
    SOLVER_CONTRACT_VERSION,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study-environment-id", required=True)
    parser.add_argument(
        "--study-phase",
        choices=("dry_run", "formative", "confirmatory", "field_pilot"),
        required=True,
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("docs/test/gate7-protocol-v1.json"),
    )
    parser.add_argument("--data-snapshot", type=Path, required=True)
    parser.add_argument(
        "--database-revision",
        required=True,
        help="Revision reported by the database used for every study session.",
    )
    parser.add_argument(
        "--frontend-build",
        type=Path,
        default=Path("frontend/dist"),
    )
    parser.add_argument(
        "--frontend-build-kind",
        choices=("h5-production", "weapp-production"),
        default="h5-production",
    )
    parser.add_argument(
        "--evidence-storage-kind",
        choices=("controlled_local", "controlled_external"),
        default="controlled_local",
    )
    parser.add_argument("--limitation", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-locked",
        action="store_true",
        help="Return non-zero when the derived status is not locked.",
    )
    args = parser.parse_args()

    protocol = load_json(_rooted(args.protocol))
    locked_hash = protocol_sha256(_rooted(args.protocol))
    snapshot_path = _rooted(args.data_snapshot)
    snapshot_meta = _published_snapshot_metadata(snapshot_path)
    JsonPublishedSolverDataProvider(snapshot_path.parent).load(snapshot_meta["version"])

    manifest = build_gate7_environment_manifest(
        protocol=protocol,
        protocol_hash=locked_hash,
        generated_at=datetime.now(UTC),
        study_environment_id=args.study_environment_id,
        study_phase=args.study_phase,
        git_state=inspect_git_state(PROJECT_ROOT),
        app_version=_app_version(),
        result_schema_version="trip-result-v2",
        solver_version=SOLVER_CONTRACT_VERSION,
        constraint_version=CONSTRAINT_VERSION,
        parameter_version=PARAMETER_VERSION,
        data_snapshot_version=snapshot_meta["version"],
        data_snapshot_kind=snapshot_meta["kind"],
        data_snapshot_sha256=_json_file_sha256(snapshot_path),
        city_id=snapshot_meta["city_id"],
        database_revision=args.database_revision,
        required_database_revision=CURRENT_DATABASE_REVISION,
        frontend_build_kind=args.frontend_build_kind,
        frontend_build_sha256=directory_sha256(_rooted(args.frontend_build)),
        evidence_storage_kind=args.evidence_storage_kind,
        limitations=list(args.limitation),
    )

    output = _rooted(args.output)
    if (
        manifest["status"] == "locked"
        and output.is_relative_to(PROJECT_ROOT)
        and not _is_git_ignored(output)
    ):
        raise ValueError(
            "a locked manifest inside the repository must be written to a Git-ignored path"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Environment: {manifest['study_environment_id']}")
    print(f"Status: {manifest['status']}")
    print(f"Manifest SHA-256: {environment_manifest_sha256(manifest)}")
    if manifest["lock_reasons"]:
        print(f"Lock reasons: {', '.join(manifest['lock_reasons'])}")
    print(f"Manifest: {output}")
    if args.require_locked and manifest["status"] != "locked":
        return 2
    return 0


def _published_snapshot_metadata(path: Path) -> dict[str, str]:
    payload = load_json(path)
    if payload.get("schema_version") != "published-solver-data-v1":
        raise ValueError("research data must use published-solver-data-v1")
    snapshot = payload.get("snapshot")
    if not isinstance(snapshot, dict):
        raise ValueError("published snapshot payload is missing")
    version = snapshot.get("version")
    city_id = snapshot.get("city_id")
    status = snapshot.get("status")
    if not isinstance(version, str) or not isinstance(city_id, str):
        raise ValueError("published snapshot version and city are required")
    if status not in {"published", "candidate"}:
        raise ValueError("published snapshot status is invalid")
    return {"version": version, "city_id": city_id, "kind": status}


def _json_file_sha256(path: Path) -> str:
    payload = load_json(path)
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _app_version() -> str:
    payload: dict[str, Any] = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return str(payload["project"]["version"])


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def _is_git_ignored(path: Path) -> bool:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={PROJECT_ROOT.as_posix()}",
            "check-ignore",
            "--quiet",
            "--no-index",
            path.relative_to(PROJECT_ROOT).as_posix(),
        ],
        cwd=PROJECT_ROOT,
        check=False,
    )
    return completed.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
