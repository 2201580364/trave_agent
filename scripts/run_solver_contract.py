"""Persist the machine-readable P1 solver contract snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.solver import DEFAULT_SOLVER_P1_CONTRACT  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/test/reports/solver-p1-contract.json"),
    )
    args = parser.parse_args()
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        **DEFAULT_SOLVER_P1_CONTRACT.to_dict(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Solver contract: {payload['contract_version']}")
    print(f"Parameter version: {payload['parameter_version']}")
    print(f"Report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
