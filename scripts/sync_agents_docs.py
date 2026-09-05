"""Sync agent entry files from the AGENTS.md canonical source.

Canonical source: AGENTS.md (project root)
Derived targets:
  - CLAUDE.md   : thin pointer (boilerplate only; canonical content NOT copied)

Usage:
    python scripts/sync_agents_docs.py          # write derived files
    python scripts/sync_agents_docs.py --check  # exit 2 if stale (CI-friendly)

Contract (transformation-plan S1-4/S2):
    - exit 0 = OK; exit 2 = violation (stale derived file); exit 1 = error
    - fail-closed: missing AGENTS.md is an error, not a silent skip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CANONICAL = PROJECT_ROOT / "AGENTS.md"

_PTR = """# trave_agent — Claude 项目入口（薄指针）

> 本文件不再是内容正本。项目上下文统一维护在 [AGENTS.md](AGENTS.md)，
> 本文件只做转发，避免两处内容漂移。

**每次会话请先读：**

1. [AGENTS.md](AGENTS.md) — 项目正本（定位、技术栈、四条核心原则、任务路由表、约束基线、关键约定）
2. [docs/process/CURRENT.md](docs/process/CURRENT.md) — 当前节点、测试基线、下一步、活跃风险

历史轮次记录在 [docs/process/status-archive/](docs/process/status-archive/)（只按需查阅）；
跨里程碑稳定路线见 [docs/process/project-roadmap.md](docs/process/project-roadmap.md)。

内容修改一律改 AGENTS.md 正本，再运行 `python scripts/sync_agents_docs.py` 同步派生物。
"""


def derive_claude_md() -> str:
    """CLAUDE.md is a pure pointer; its content is fixed boilerplate."""
    return _PTR


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify derived files are up to date")
    args = parser.parse_args()

    if not CANONICAL.is_file():
        print("ERROR: AGENTS.md not found at project root", file=sys.stderr)
        return 1
    canonical_lines = len(CANONICAL.read_text(encoding="utf-8-sig").splitlines())
    if canonical_lines == 0:
        print("ERROR: canonical AGENTS.md is empty", file=sys.stderr)
        return 1

    claude_path = PROJECT_ROOT / "CLAUDE.md"
    expected_claude = derive_claude_md()
    violations: list[str] = []

    if args.check:
        if claude_path.is_file():
            current = claude_path.read_text(encoding="utf-8-sig")
            if current != expected_claude:
                violations.append("CLAUDE.md 与 AGENTS.md 正本派生关系漂移（内容与模板不一致）")
        else:
            violations.append("CLAUDE.md 缺失")
        if violations:
            for v in violations:
                print(f"VIOLATION: {v}")
            print("Run `python scripts/sync_agents_docs.py` to fix.", file=sys.stderr)
            return 2
        print(f"OK: derived files up to date (AGENTS.md {canonical_lines} lines)")
        return 0

    claude_path.write_text(expected_claude, encoding="utf-8-sig")
    print(f"OK: CLAUDE.md pointer regenerated ({canonical_lines} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
