"""Contract tests for scripts/check_layering.py (transformation-plan S3-4).

Validates that the architecture layering gate catches intentionally injected
violations:
  - domain importing an outer layer (interfaces);
  - domain importing a third-party framework;
  - solver importing infrastructure;
  - application importing interfaces;
  - an unregistered module importing infrastructure.

The gate operates on a synthetic package tree built in tmp_path so the tests
never touch the real source tree.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_layering  # noqa: E402


@pytest.fixture()
def pkg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal valid travel_agent package and point the gate at it."""
    src = tmp_path / "src" / "travel_agent"
    layers = (
        "domain/planning",
        "application/planning",
        "interfaces/http",
        "solver",
        "infrastructure/database",
    )
    for layer in layers:
        (src / layer).mkdir(parents=True, exist_ok=True)
    inits = (
        "domain",
        "application",
        "interfaces",
        "solver",
        "infrastructure",
        "infrastructure/database",
    )
    for layer in inits:
        (src / layer / "__init__.py").write_text("", encoding="utf-8")

    # Valid layering: interfaces -> application -> domain; solver is clean.
    (src / "domain" / "planning" / "entities.py").write_text(
        "from dataclasses import dataclass\n\n\n@dataclass\nclass Trip:\n    pass\n",
        encoding="utf-8",
    )
    (src / "application" / "planning" / "handlers.py").write_text(
        "from travel_agent.domain.planning.entities import Trip\n",
        encoding="utf-8",
    )
    (src / "interfaces" / "http" / "app.py").write_text(
        "from travel_agent.application.planning.handlers import Trip\n",
        encoding="utf-8",
    )
    (src / "solver" / "engine.py").write_text(
        "from travel_agent.domain.planning.entities import Trip\n",
        encoding="utf-8",
    )
    (src / "infrastructure" / "database" / "repo.py").write_text(
        "from travel_agent.domain.planning.entities import Trip\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(check_layering, "ROOT", tmp_path)
    monkeypatch.setattr(check_layering, "SRC", src)
    return src


def _run() -> check_layering.Report:
    return check_layering.run()


def _rules(report: check_layering.Report) -> list[str]:
    return [v.rule for v in report.violations]


def test_valid_baseline_passes(pkg: Path) -> None:
    report = _run()
    assert report.passed, [vars(v) for v in report.violations]
    assert report.scanned_files > 0


def test_domain_importing_interfaces_is_violation(pkg: Path) -> None:
    (pkg / "domain" / "planning" / "entities.py").write_text(
        "from travel_agent.interfaces.http.app import create_app\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    assert "no-import-interfaces" in _rules(report)


def test_domain_importing_framework_is_violation(pkg: Path) -> None:
    (pkg / "domain" / "planning" / "entities.py").write_text(
        "from sqlalchemy.orm import Session\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    assert "domain-framework-free" in _rules(report)


def test_solver_importing_infrastructure_is_violation(pkg: Path) -> None:
    (pkg / "solver" / "engine.py").write_text(
        "from travel_agent.infrastructure.database.repo import Repo\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    assert "solver-io-free" in _rules(report)


def test_application_importing_interfaces_is_violation(pkg: Path) -> None:
    (pkg / "application" / "planning" / "handlers.py").write_text(
        "from travel_agent.interfaces.http.app import create_app\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    assert "no-import-interfaces" in _rules(report)


def test_unregistered_module_importing_infrastructure_is_violation(pkg: Path) -> None:
    (pkg / "application" / "planning" / "handlers.py").write_text(
        "from travel_agent.infrastructure.database.repo import Repo\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    assert "infra-composition-only" in _rules(report)


def test_exemption_file_may_import_infrastructure(
    pkg: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = pkg.parents[1]  # tmp_path/src/travel_agent -> tmp_path
    local_dev = root / "src" / "travel_agent" / "local_dev.py"
    local_dev.write_text(
        "from travel_agent.infrastructure.database.repo import Repo\n"
        "from travel_agent.interfaces.http.app import create_app\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        check_layering,
        "INFRA_EXEMPT_FILES",
        {"src/travel_agent/local_dev.py"},
    )
    monkeypatch.setattr(
        check_layering,
        "INTERFACES_EXEMPT_FILES",
        {"src/travel_agent/local_dev.py"},
    )
    report = _run()
    assert report.passed, [vars(v) for v in report.violations]


def test_same_layer_import_is_legal(pkg: Path) -> None:
    # application/common imported by application/planning: same layer, fine.
    common = pkg / "application" / "common"
    common.mkdir(exist_ok=True)
    (common / "__init__.py").write_text("", encoding="utf-8")
    (common / "clock.py").write_text("CLOCK = 1\n", encoding="utf-8")
    (pkg / "application" / "planning" / "handlers.py").write_text(
        "from travel_agent.application.common.clock import CLOCK\n",
        encoding="utf-8",
    )
    report = _run()
    assert report.passed, [vars(v) for v in report.violations]
