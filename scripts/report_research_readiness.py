"""Report governed research Place readiness without mutating the database."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from travel_agent.data_governance.research_readiness import (  # noqa: E402
    load_research_readiness,
    render_research_readiness_markdown,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / ".local" / "research.db",
        help="SQLite research database",
    )
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=[],
        help="limit the report to this hz-cand ID; repeat for a controlled batch",
    )
    parser.add_argument(
        "--lifecycle-status",
        choices=("candidate", "human_verified", "published"),
        help="limit the report to one lifecycle status",
    )
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()

    try:
        report = load_research_readiness(
            args.database,
            candidate_ids=tuple(args.candidate_id),
            lifecycle_status=args.lifecycle_status,
        )
    except ValueError as exc:
        parser.error(str(exc))
    if args.format == "json":
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_research_readiness_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
