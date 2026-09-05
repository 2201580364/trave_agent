"""Documentation governance gate for the trave_agent knowledge base.

Detects documentation drift mechanically instead of relying on discipline.
Style contract aligned with audit_catalog_boundaries.py:
  - fail-closed;
  - exit code 0 = pass, 2 = violations found, 1 = execution error;
  - --json emits a machine-readable report.

Checks (transformation-plan S2):
  1. Empty ADRs (<10 non-empty lines) and ADR number collisions.
  2. "当前节点" consistency across CLAUDE.md / AGENTS.md / CURRENT.md / README.md.
  3. ADR references used in .claude rules (and future .cursor rules) must resolve
     to an existing, non-empty ADR file in docs/decisions/.
  4. CURRENT.md line budget (<=150 lines; exceeding warns and suggests archiving);
     project-status.md is append-only by convention (exempted, enforced by discipline).
  5. (Deferred until S5, if a docs/ai/manifest is ever created) manifest <-> directory
     bidirectional consistency. Not implemented on purpose: no manifest exists yet
     and a self-maintained checklist without a gate is worse than none.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ADR_RE = re.compile(r"\bADR-(\d{4})\b")
CURRENT_NODE_RE = re.compile(r"当前节点[：:]\s*`([^`]+)`")
# Node value that is allowed to appear in derived L0 entries (pointers, not statements).
POINTER_NODE_PATTERN = re.compile(r"当前节点.*CURRENT", re.IGNORECASE)

DECISIONS_DIR = ROOT / "docs" / "decisions"
CURRENT_MD = ROOT / "docs" / "process" / "CURRENT.md"
STATUS_LEDGER = ROOT / "docs" / "project-status.md"
RULE_DIRS = [ROOT / ".claude" / "rules", ROOT / ".cursor" / "rules"]

CURRENT_LINE_BUDGET = 150
ADR_MIN_NONEMPTY_LINES = 10


@dataclass
class CheckResult:
    check_id: str
    title: str
    passed: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class Report:
    passed: bool = True
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, check: CheckResult) -> None:
        self.checks.append(check)
        if check.violations:
            self.passed = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [
                {
                    "id": c.check_id,
                    "title": c.title,
                    "passed": c.passed,
                    "violations": c.violations,
                    "warnings": c.warnings,
                }
                for c in self.checks
            ],
        }


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


# ---------------------------------------------------------------- check 1
def check_adrs(report: Report) -> None:
    """Empty ADRs and number collisions."""
    result = CheckResult("adr-integrity", "ADR 空文件与编号冲突检查")
    if not DECISIONS_DIR.is_dir():
        result.violations.append(f"missing directory: {DECISIONS_DIR}")
        result.passed = False
        report.add(result)
        return

    numbers: dict[str, list[str]] = {}
    empty: list[str] = []
    for adr in sorted(DECISIONS_DIR.glob("ADR-*.md")):
        m = re.match(r"^ADR-(\d{4})-", adr.name)
        if not m:
            continue
        num = f"ADR-{m.group(1)}"
        numbers.setdefault(num, []).append(adr.name)
        nonempty = [ln for ln in read_text(adr).splitlines() if ln.strip()]
        if len(nonempty) < ADR_MIN_NONEMPTY_LINES:
            empty.append(f"{adr.name} ({len(nonempty)} non-empty lines)")

    for num, files in sorted(numbers.items()):
        if len(files) > 1:
            result.violations.append(f"编号冲突 {num}: {', '.join(files)}")
    for e in empty:
        result.violations.append(f"疑似空 ADR: {e}")
    result.passed = not result.violations
    report.add(result)


# ---------------------------------------------------------------- check 2
def _extract_node_statement(text: str, label: str, required: bool) -> tuple[str | None, list[str]]:
    """Return (canonical_node, problems). A statement line is `当前节点：`...``.

    Pointer-style mentions (e.g. CLAUDE.md '当前节点…CURRENT.md') are not
    statements of state and are ignored. Only the canonical file (CURRENT.md)
    is required to carry a statement; derived files may omit it entirely.
    """
    problems: list[str] = []
    statements: list[str] = []
    for line in text.splitlines():
        m = CURRENT_NODE_RE.search(line)
        if not m:
            continue
        if POINTER_NODE_PATTERN.search(line):
            continue
        statements.append(m.group(1))
    if required and len(statements) == 0:
        problems.append(f"{label}: 未找到「当前节点」声明（应为唯一权威声明处）")
    if len(statements) > 1:
        problems.append(f"{label}: 发现 {len(statements)} 处声明（应为至多 1 处）: {statements}")
    return (statements[0] if statements else None), problems


def check_current_node_consistency(report: Report) -> None:
    """'当前节点' must appear at most once per file and consistently across files."""
    result = CheckResult("current-node-consistency", "当前节点一致性检查（L0 入口文件 vs CURRENT）")
    files = {
        "CLAUDE.md": ROOT / "CLAUDE.md",
        "AGENTS.md": ROOT / "AGENTS.md",
        "CURRENT.md": CURRENT_MD,
        "README.md": ROOT / "README.md",
    }
    nodes: dict[str, str] = {}
    for label, path in files.items():
        if not path.is_file():
            result.violations.append(f"{label}: 文件缺失 ({path})")
            continue
        is_canonical = label == "CURRENT.md"
        node, problems = _extract_node_statement(read_text(path), label, required=is_canonical)
        result.violations.extend(problems)
        if node:
            nodes[label] = node

    # CURRENT.md is the canonical source; every other statement must match it.
    canonical = nodes.get("CURRENT.md")
    if canonical:
        for label, node in nodes.items():
            if label != "CURRENT.md" and node != canonical:
                result.violations.append(
                    f"{label}: 节点「{node}」与 CURRENT.md「{canonical}」不一致"
                )
    result.passed = not result.violations
    report.add(result)


# ---------------------------------------------------------------- check 3
def check_rules_adr_references(report: Report) -> None:
    """ADR ids referenced in agent rule files must exist as non-empty ADRs."""
    result = CheckResult("rules-adr-references", "rules 中 ADR 引用闭环检查")
    existing: dict[str, int] = {}
    if DECISIONS_DIR.is_dir():
        for adr in DECISIONS_DIR.glob("ADR-*.md"):
            m = re.match(r"^ADR-(\d{4})-", adr.name)
            if m:
                nonempty = len([ln for ln in read_text(adr).splitlines() if ln.strip()])
                existing[f"ADR-{m.group(1)}"] = nonempty

    scanned_any = False
    for rule_dir in RULE_DIRS:
        if not rule_dir.is_dir():
            continue
        for md in rule_dir.rglob("*.md"):
            scanned_any = True
            text = read_text(md)
            for num in ADR_RE.findall(text):
                adr_id = f"ADR-{num}"
                if adr_id not in existing:
                    result.violations.append(f"{md.relative_to(ROOT)}: 引用了不存在的 {adr_id}")
                elif existing[adr_id] < ADR_MIN_NONEMPTY_LINES:
                    result.violations.append(f"{md.relative_to(ROOT)}: 引用了疑似空的 {adr_id}")
    if not scanned_any:
        result.warnings.append("未扫描到任何 rules 目录（.claude/rules 缺失？）")
    result.passed = not result.violations
    report.add(result)


# ---------------------------------------------------------------- check 4
def check_current_line_budget(report: Report) -> None:
    """CURRENT.md must stay within budget (warning only)."""
    result = CheckResult("current-line-budget", "CURRENT.md 行数预算检查（≤150 行）")
    if not CURRENT_MD.is_file():
        result.violations.append(f"CURRENT.md 缺失: {CURRENT_MD}")
        result.passed = False
        report.add(result)
        return
    n = len(read_text(CURRENT_MD).splitlines())
    if n > CURRENT_LINE_BUDGET:
        hint = f"CURRENT.md 已 {n} 行（预算 {CURRENT_LINE_BUDGET}），请归档旧条目到 status-archive/"
        result.warnings.append(hint)
    result.passed = not result.violations
    report.add(result)


# ---------------------------------------------------------------- main
def run_checks() -> Report:
    report = Report()
    check_adrs(report)
    check_current_node_consistency(report)
    check_rules_adr_references(report)
    check_current_line_budget(report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    try:
        report = run_checks()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for c in report.checks:
            status = "PASS" if c.passed and not c.warnings else ("WARN" if c.passed else "FAIL")
            print(f"[{status}] {c.check_id}: {c.title}")
            for v in c.violations:
                print(f"    - violation: {v}")
            for w in c.warnings:
                print(f"    - warning:   {w}")
        print("RESULT:", "PASS" if report.passed else "FAIL")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
