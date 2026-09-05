"""Contract tests for scripts/check_docs.py (transformation-plan S2 exit criteria).

Validates that the documentation gate catches intentionally injected drift:
  - node drift between CURRENT.md and another entry file;
  - empty ADR / ADR number collision;
  - dangling ADR reference in agent rules;
  - CURRENT.md line budget warning.

The gate is imported with monkeypatched ROOT so the tests never mutate the real
knowledge base.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_docs  # noqa: E402


@pytest.fixture()
def kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a minimal, valid knowledge base and point check_docs at it."""
    decisions = tmp_path / "docs" / "decisions"
    process = tmp_path / "docs" / "process"
    rules = tmp_path / ".claude" / "rules"
    for d in (decisions, process, rules):
        d.mkdir(parents=True)

    adr_body = (
        "# ADR-0001：示例\n\n状态：已接受\n\n## 背景\n\n这里是需要足够行数的背景说明，"
        "用于确保该 ADR 不会被空文件检查误报。\n\n## 决策\n\n这里记录具体决策内容。\n\n"
        "## 取舍\n\n这里记录取舍。\n\n## 验收条件\n\n这里记录验收条件。\n"
    )
    (decisions / "ADR-0001-example.md").write_text(adr_body, encoding="utf-8")
    (decisions / "ADR-0002-example.md").write_text(
        adr_body.replace("ADR-0001", "ADR-0002"), encoding="utf-8"
    )

    current = "\n".join(
        [
            "# CURRENT — 当前状态滚动快照",
            "",
            "- 更新时间：2026-09-05",
            "- 当前节点：`M1 / Gate 7 / G7-R0.2-05-03`",
        ]
    ) + "\n"
    (process / "CURRENT.md").write_text(current, encoding="utf-8")

    claude = (
        "# Claude 入口\n\n读 [AGENTS.md](AGENTS.md) 与 [CURRENT.md](docs/process/CURRENT.md)。\n"
    )
    (tmp_path / "CLAUDE.md").write_text(claude, encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n\n正本。\n", encoding="utf-8")
    readme = "# README\n\n状态见 CURRENT.md，不在此复述节点。\n"
    (tmp_path / "README.md").write_text(readme, encoding="utf-8")

    (rules / "solver.md").write_text("# 求解器规则\n\n参见 ADR-0001。\n", encoding="utf-8")

    monkeypatch.setattr(check_docs, "ROOT", tmp_path)
    monkeypatch.setattr(check_docs, "DECISIONS_DIR", decisions)
    monkeypatch.setattr(check_docs, "CURRENT_MD", process / "CURRENT.md")
    monkeypatch.setattr(check_docs, "RULE_DIRS", [rules])
    return tmp_path


def _run() -> check_docs.Report:
    return check_docs.run_checks()


def test_valid_baseline_passes(kb: Path) -> None:
    report = _run()
    assert report.passed, [v for c in report.checks for v in c.violations]


def test_detects_node_drift_between_current_and_readme(kb: Path) -> None:
    readme = kb / "README.md"
    readme.write_text(
        "# README\n\n- 当前节点：`M2 / 已完成`\n",
        encoding="utf-8",
    )
    report = _run()
    assert not report.passed
    drift = [c for c in report.checks if c.check_id == "current-node-consistency"]
    assert drift and drift[0].violations
    assert any("不一致" in v for v in drift[0].violations)


def test_detects_duplicate_current_node_statements(kb: Path) -> None:
    current = kb / "docs" / "process" / "CURRENT.md"
    text = current.read_text(encoding="utf-8-sig")
    current.write_text(text + "- 当前节点：`另一个节点`\n", encoding="utf-8-sig")
    report = _run()
    assert not report.passed
    drift = [c for c in report.checks if c.check_id == "current-node-consistency"]
    assert any("至多 1 处" in v for v in drift[0].violations)


def test_detects_empty_adr(kb: Path) -> None:
    adr = kb / "docs" / "decisions" / "ADR-0009-empty.md"
    adr.write_text("# ADR-0009：空\n\n（待补）\n", encoding="utf-8")
    report = _run()
    assert not report.passed
    integrity = [c for c in report.checks if c.check_id == "adr-integrity"]
    assert any("ADR-0009-empty" in v for v in integrity[0].violations)


def test_detects_adr_number_collision(kb: Path) -> None:
    decisions = kb / "docs" / "decisions"
    body = (
        "# ADR-0001：冲突\n\n状态：已接受\n\n## 背景\n\n这里是需要足够行数的背景说明。\n\n"
        "## 决策\n\n决策内容。\n\n## 取舍\n\n取舍说明。\n\n## 验收条件\n\n验收说明。\n"
    )
    (decisions / "ADR-0001-collision.md").write_text(body, encoding="utf-8")
    report = _run()
    assert not report.passed
    integrity = [c for c in report.checks if c.check_id == "adr-integrity"]
    assert any("编号冲突 ADR-0001" in v for v in integrity[0].violations)


def test_detects_dangling_adr_reference_in_rules(kb: Path) -> None:
    rules = kb / ".claude" / "rules"
    (rules / "traceability.md").write_text("# 规则\n\n参见 ADR-0099。\n", encoding="utf-8")
    report = _run()
    assert not report.passed
    refs = [c for c in report.checks if c.check_id == "rules-adr-references"]
    assert any("ADR-0099" in v for v in refs[0].violations)


def test_warns_when_current_exceeds_line_budget(kb: Path) -> None:
    current = kb / "docs" / "process" / "CURRENT.md"
    lines = current.read_text(encoding="utf-8-sig").splitlines()
    padding = [f"- 历史条目 {i}" for i in range(check_docs.CURRENT_LINE_BUDGET)]
    current.write_text("\n".join(lines + padding) + "\n", encoding="utf-8-sig")
    report = _run()
    # Over-budget is a warning, not a failure.
    assert report.passed
    budget = [c for c in report.checks if c.check_id == "current-line-budget"]
    assert budget and budget[0].warnings


def test_missing_current_md_is_violation(kb: Path) -> None:
    (kb / "docs" / "process" / "CURRENT.md").unlink()
    report = _run()
    assert not report.passed
