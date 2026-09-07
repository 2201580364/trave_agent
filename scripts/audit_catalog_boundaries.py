"""Audit a catalog database before using it for research or browser validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from travel_agent.data_governance.catalog_audit import audit_catalog_database  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database",
        type=Path,
        default=ROOT / ".local" / "travel_agent.db",
        help="SQLite catalog database to audit",
    )
    parser.add_argument(
        "--human",
        action="store_true",
        help="print a human-readable summary in addition to the JSON payload",
    )
    args = parser.parse_args()
    database = args.database.resolve()
    if not database.exists():
        print(
            json.dumps(
                {"status": "error", "error": f"database not found: {database}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    report = audit_catalog_database(database)
    payload = report.to_dict()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.human:
        print(
            f"audit {'passed' if report.passed else 'failed'}: "
            f"{len(payload.get('violations', []))} violation(s)",
            file=sys.stderr,
        )
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
