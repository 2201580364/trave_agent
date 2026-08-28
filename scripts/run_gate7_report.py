"""Validate anonymized Gate 7 evidence and write an aggregate-only report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.evaluation import build_gate7_report, protocol_sha256  # noqa: E402
from travel_agent.evaluation.gate7 import load_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("docs/test/gate7-protocol-v1.json"),
    )
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--require-h3-supported",
        action="store_true",
        help="Return a non-zero exit code unless formal H3 evidence is supported.",
    )
    args = parser.parse_args()

    locked_hash = protocol_sha256(args.protocol)
    protocol = load_json(args.protocol)
    evidence = load_json(args.evidence)
    report = build_gate7_report(
        protocol,
        evidence,
        expected_protocol_hash=locked_hash,
        generated_at=datetime.now(UTC),
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Study: {report['study_id']}")
    print(f"H3 status: {report['hypotheses']['H3']['status']}")
    print(f"H11 status: {report['hypotheses']['H11']['status']}")
    print(f"Report: {args.output}")

    if args.require_h3_supported:
        return 0 if report["hypotheses"]["H3"]["status"] == "supported" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
