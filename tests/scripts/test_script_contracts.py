"""Script-contract tests for the S5-3 hardened scripts (transformation-plan S5-4).

Contract under test (``.claude/rules/script-contract.md``):

- stable exit codes: 0 success / 1 runtime error / 2 check failure;
- ``--json`` emits a single parseable JSON object with a verdict field;
- read-only scripts never mutate inputs; ``--dry-run`` leaves no persistent change.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "scripts"

#: Scripts whose contract behaviour is asserted here. Each must expose ``--json``.
CONTRACT_SCRIPTS = (
    "report_research_readiness.py",
    "audit_catalog_boundaries.py",
    "validate_candidate_catalog.py",
)


def _run(script: str, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=PROJECT_ROOT,
    )


def test_golden_cases_json_stdout_contract() -> None:
    result = _run(
        "run_golden_cases.py",
        "--json",
        "--output",
        "var/reports/gate6-golden-contract-test.json",
    )
    assert result.returncode in (0, 2), result.stderr
    payload = json.loads(result.stdout)
    assert payload["suite"] == "hangzhou-realistic-golden-cases"
    assert isinstance(payload["gate_passed"], bool)
    assert payload["gate_passed"] == (result.returncode == 0)
    assert payload["total"] > 0
    # The verdict must be internally consistent with the per-case results.
    assert payload["passed"] <= payload["total"]


@pytest.mark.parametrize("script", CONTRACT_SCRIPTS)
def test_missing_database_exits_nonzero(script: str) -> None:
    result = _run(script, "--database", "var/does-not-exist-contract-test.db")
    assert result.returncode != 0


def test_audit_catalog_boundaries_json_verdict_on_missing_db() -> None:
    result = _run(
        "audit_catalog_boundaries.py", "--database", "var/does-not-exist-contract-test.db"
    )
    assert result.returncode == 1
    payload = json.loads(result.stderr)
    assert payload["status"] == "error"
    assert "database not found" in payload["error"]


def test_validate_candidate_catalog_default_inputs_pass(tmp_path: Path) -> None:
    result = _run("validate_candidate_catalog.py", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["candidate_count"] > 0


def test_validate_candidate_catalog_missing_file_is_error(tmp_path: Path) -> None:
    result = _run(
        "validate_candidate_catalog.py",
        "--json",
        "--catalog",
        str(tmp_path / "missing-catalog.json"),
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"


def test_validate_candidate_catalog_invalid_registry_is_check_failure(
    tmp_path: Path,
) -> None:
    catalog_path = PROJECT_ROOT / "data/governance/hangzhou-candidate-catalog-v1.json"
    coverage_path = PROJECT_ROOT / "data/governance/hangzhou-candidate-coverage-v1.json"
    dictionary_path = PROJECT_ROOT / "data/governance/place-collection-field-dictionary-v1.json"
    broken_registry = tmp_path / "broken-registry.json"
    broken_registry.write_text("{}", encoding="utf-8")

    result = _run(
        "validate_candidate_catalog.py",
        "--json",
        "--catalog",
        str(catalog_path),
        "--coverage",
        str(coverage_path),
        "--registry",
        str(broken_registry),
        "--field-dictionary",
        str(dictionary_path),
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"


def test_import_candidate_revisions_dry_run_writes_nothing(tmp_path: Path) -> None:
    database = tmp_path / "contract-dry-run.db"
    result = _run(
        "import_candidate_revisions.py",
        "--dry-run",
        "--json",
        "--database",
        str(database),
        "--candidate-id",
        "hz-cand-003",
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["dry_run"] is True
    assert payload["imported"] == 1
    # L2 contract: --dry-run must not create or modify the database file.
    assert not database.exists()


def test_report_research_readiness_json_flag_matches_format_json(
    tmp_path: Path,
) -> None:
    database = tmp_path / "missing-research.db"
    shorthand = _run("report_research_readiness.py", "--json", "--database", str(database))
    explicit = _run("report_research_readiness.py", "--format", "json", "--database", str(database))
    assert shorthand.returncode == explicit.returncode
    assert shorthand.returncode != 0
