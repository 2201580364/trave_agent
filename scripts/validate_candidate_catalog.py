"""Validate the tracked R0.2-04 candidate catalog and coverage matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.data_governance import (  # noqa: E402
    CandidateCatalogError,
    load_json_object,
    validate_candidate_catalog,
    validate_candidate_coverage,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--catalog",
        type=Path,
        default=Path("data/governance/hangzhou-candidate-catalog-v1.json"),
    )
    parser.add_argument(
        "--coverage",
        type=Path,
        default=Path("data/governance/hangzhou-candidate-coverage-v1.json"),
    )
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("data/governance/hangzhou-source-registry-v1.json"),
    )
    parser.add_argument(
        "--field-dictionary",
        type=Path,
        default=Path("data/governance/place-collection-field-dictionary-v1.json"),
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    catalog = load_json_object(_rooted(args.catalog))
    coverage = load_json_object(_rooted(args.coverage))
    registry = load_json_object(_rooted(args.registry))
    dictionary = load_json_object(_rooted(args.field_dictionary))
    try:
        validate_candidate_catalog(catalog, registry, dictionary)
        validate_candidate_coverage(coverage, catalog)
    except CandidateCatalogError as exc:
        print(f"candidate catalog validation failed: {exc}", file=sys.stderr)
        return 1

    summary = {
        "status": "valid",
        "catalog_id": catalog["catalog_id"],
        "candidate_count": len(catalog["candidates"]),
        "relation_clue_count": len(catalog["relation_clues"]),
        **coverage["actuals"],
        "exit_evaluation": coverage["exit_evaluation"]["status"],
    }
    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        for key, value in summary.items():
            print(f"{key}={value}")
    return 0


def _rooted(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
