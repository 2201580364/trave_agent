"""Architecture layering gate for the trave_agent codebase.

Enforces the dependency rules documented in docs/product/应用代码架构设计.md:
  1. `interfaces` and `application` may be imported by outer layers only;
     dependency direction must be interfaces -> application -> domain.
  2. `solver/` must NOT import `infrastructure/` (the solver is a deterministic
     engine; IO lives behind ports provided by domain/application contracts).
  3. `domain/` must stay free of external frameworks (no sqlalchemy/fastapi/
     pydantic/redis imports) — it is the pure core.
  4. Nobody may import from `interfaces` (the HTTP edge is a leaf, never a
     library) except tests and scripts.

Style contract aligned with check_docs.py / audit_catalog_boundaries.py:
  - fail-closed; exit 0 = pass, 2 = violation, 1 = error; --json output.

This intentionally uses AST scanning instead of adding import-linter as a new
dependency (project rule: new third-party dependencies require an ADR).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "travel_agent"

# Layer ordering (outermost -> innermost). A layer may only import layers at
# or inside (i.e. after it in) this tuple. Same-layer imports are always legal.
LAYER_ORDER = ("interfaces", "application", "domain")
# Sub-packages that live outside the classic three-layer core and may be
# consumed by application/infrastructure (they are leaf utilities or engines).
AUX_PACKAGES = {"solver", "observability", "data_governance", "evaluation", "runtime_config"}
# Layers allowed to import infrastructure adapters (composition roots).
INFRA_CONSUMERS = {"interfaces", "infrastructure"}
# Explicitly registered composition roots / read-only report tools that are
# allowed to assemble infrastructure adapters outside INFRA_CONSUMERS.
# Keep this list short and intentional: every entry must be a genuine
# composition root (assembles the object graph) or a script-like reporter.
INFRA_EXEMPT_FILES = {
    "src/travel_agent/local_dev.py",  # local dev composition root (self-declared)
    "src/travel_agent/data_governance/research_readiness.py",  # read-only report tool
}
INTERFACES_EXEMPT_FILES = {
    "src/travel_agent/local_dev.py",  # mounts the HTTP app locally
}

FORBIDDEN_IN_SOLVER = re.compile(r"^travel_agent\.infrastructure(\.|$)")
FORBIDDEN_IN_DOMAIN = ("sqlalchemy", "fastapi", "pydantic", "redis", "uvicorn", "httpx")
# Modules that may appear in domain type hints through the stdlib typing system
# are irrelevant; only real third-party framework imports are forbidden.


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    detail: str


@dataclass
class Report:
    passed: bool = True
    scanned_files: int = 0
    violations: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "scanned_files": self.scanned_files,
            "violations": [vars(v) for v in self.violations],
        }


def _iter_imports(tree: ast.AST) -> list[tuple[int, str]]:
    """Yield (lineno, module) for import / from-import statements."""
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imports.append((node.lineno, node.module))
    return imports


def _layer_of(module: str) -> str | None:
    """Return the travel_agent sub-package layer for a module path."""
    if not module.startswith("travel_agent."):
        return None
    parts = module.split(".")
    if len(parts) < 2:
        return None
    return parts[1]


def _layer_index(module: str) -> int | None:
    """Return position in LAYER_ORDER for a travel_agent sub-package, or None."""
    if not module.startswith("travel_agent."):
        return None
    parts = module.split(".")
    if len(parts) < 2:
        return None
    sub = parts[1]
    if sub in LAYER_ORDER:
        return LAYER_ORDER.index(sub)
    return None


def check_file(path: Path, report: Report) -> None:
    rel = path.relative_to(ROOT).as_posix()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except SyntaxError as exc:
        lineno = getattr(exc, "lineno", 0) or 0
        report.violations.append(Violation(rel, lineno, "syntax", f"无法解析: {exc}"))
        return

    file_layer = path.parent.relative_to(SRC).parts[0] if path.parent != SRC else None
    file_idx = LAYER_ORDER.index(file_layer) if file_layer in LAYER_ORDER else None

    for lineno, module in _iter_imports(tree):
        # Rule 4: nobody inside src/ imports travel_agent.interfaces (leaf edge).
        is_ifaces = re.match(r"^travel_agent\.interfaces(\.|$)", module)
        if is_ifaces and rel not in INTERFACES_EXEMPT_FILES:
            detail = f"禁止 import {module}（HTTP 边界是叶子，不是库）"
            report.violations.append(Violation(rel, lineno, "no-import-interfaces", detail))
            continue

        # Rule 2: solver must not import infrastructure.
        if file_layer == "solver" and FORBIDDEN_IN_SOLVER.match(module):
            report.violations.append(
                Violation(rel, lineno, "solver-io-free", f"solver 不得 import {module}")
            )
            continue

        # Rule infra: only composition roots (interfaces / infrastructure
        # itself, plus explicitly registered roots) may import infrastructure.
        if re.match(r"^travel_agent\.infrastructure(\.|$)", module):
            if file_layer not in INFRA_CONSUMERS and rel not in INFRA_EXEMPT_FILES:
                layer_name = file_layer or "root"
                detail = f"{layer_name} 不得 import {module}（基础设施只允许组合根装配）"
                report.violations.append(Violation(rel, lineno, "infra-composition-only", detail))
            continue

        # Rule 1: classic layer direction interfaces -> application -> domain.
        if file_idx is not None:
            target_idx = _layer_index(module)
            if target_idx is not None and target_idx < file_idx:
                report.violations.append(
                    Violation(
                        rel,
                        lineno,
                        "layer-direction",
                        f"{file_layer} 不得 import {module}（依赖只能指向更内层）",
                    )
                )

        # Rule 3: domain stays framework-free.
        if file_layer == "domain" and module.split(".")[0] in FORBIDDEN_IN_DOMAIN:
            detail = f"domain 不得 import 第三方框架 {module}"
            report.violations.append(Violation(rel, lineno, "domain-framework-free", detail))


def run() -> Report:
    report = Report()
    for path in sorted(SRC.rglob("*.py")):
        report.scanned_files += 1
        check_file(path, report)
    report.passed = not report.violations
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    args = parser.parse_args()

    try:
        report = run()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        for v in report.violations:
            print(f"VIOLATION [{v.rule}] {v.file}:{v.line}  {v.detail}")
        print(f"Scanned {report.scanned_files} files, {len(report.violations)} violations")
        print("RESULT:", "PASS" if report.passed else "FAIL")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
