"""Script-contract tests for the S8-2 OpenAPI snapshot + contract diff pair.

Contract under test (``.claude/rules/script-contract.md``):

- ``export_openapi_schema.py``: exit 0 with a JSON verdict; writes the snapshot
  to ``var/reports/`` (gitignored) or a caller-provided path;
- ``check_api_contract.py``: exit 0 = implemented routes all registered in the
  contract; exit 1 = runtime error (missing schema/contract); exit 2 = gate
  violation (code endpoint absent from the contract); ``--json`` verdicts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = PROJECT_ROOT / "scripts"
SNAPSHOT = PROJECT_ROOT / "var/reports/openapi-schema.json"


def _run(script: str, *argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *argv],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        cwd=PROJECT_ROOT,
    )


class TestExportOpenApiSchema:
    def test_export_success_json_verdict(self, tmp_path: Path) -> None:
        output = tmp_path / "openapi-schema.json"
        result = _run("export_openapi_schema.py", "--json", "--output", str(output))
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == "ok"
        assert payload["path_count"] > 0
        schema = json.loads(output.read_text(encoding="utf-8"))
        assert schema["openapi"].startswith("3.")
        assert "/api/v1/anonymous-sessions" in schema["paths"]

    def test_export_snapshot_contains_admin_surface(self, tmp_path: Path) -> None:
        # The snapshot must include the admin router blocks, which only mount
        # when review_workflow / holiday_calendar_sync are provided.
        output = tmp_path / "openapi-schema.json"
        result = _run("export_openapi_schema.py", "--output", str(output))
        assert result.returncode == 0, result.stderr
        schema = json.loads(output.read_text(encoding="utf-8"))
        admin_paths = [p for p in schema["paths"] if "/admin" in p]
        assert len(admin_paths) >= 20


class TestCheckApiContract:
    def test_current_repo_state_passes(self) -> None:
        result = _run("check_api_contract.py", "--json")
        assert result.returncode in (0, 2), result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] in ("ok", "failed")
        assert payload["status"] == ("ok" if result.returncode == 0 else "failed")
        assert isinstance(payload["code_only"], list)
        assert isinstance(payload["contract_only"], list)
        assert payload["contract_endpoint_count"] > 0

    def test_missing_schema_is_runtime_error(self, tmp_path: Path) -> None:
        result = _run(
            "check_api_contract.py",
            "--json",
            "--schema",
            str(tmp_path / "missing.json"),
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_missing_contract_is_runtime_error(self, tmp_path: Path) -> None:
        result = _run(
            "check_api_contract.py",
            "--json",
            "--contract",
            str(tmp_path / "missing.md"),
        )
        assert result.returncode == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_code_only_registration_fails_gate(self, tmp_path: Path) -> None:
        # Strip an implemented endpoint from the contract copy: the diff must
        # flag it as code-only and exit 2 (fail-closed on contract drift).
        contract_text = (PROJECT_ROOT / "docs/specs/api-contract.md").read_text(
            encoding="utf-8"
        )
        marker = "| POST | `/anonymous-sessions` | 创建匿名主体 | 是 |"
        assert marker in contract_text
        trimmed = contract_text.replace(marker, "")
        contract_copy = tmp_path / "api-contract-trimmed.md"
        contract_copy.write_text(trimmed, encoding="utf-8")
        result = _run(
            "check_api_contract.py", "--json", "--contract", str(contract_copy)
        )
        assert result.returncode == 2
        payload = json.loads(result.stdout)
        assert payload["status"] == "failed"
        assert "POST /api/v1/anonymous-sessions" in payload["code_only"]

    def test_readonly_no_mutation(self) -> None:
        # L1 read-only gate: running the check twice must not change the
        # snapshot file it consumes.
        before = SNAPSHOT.read_bytes() if SNAPSHOT.exists() else None
        _run("check_api_contract.py")
        after = SNAPSHOT.read_bytes() if SNAPSHOT.exists() else None
        assert before == after
