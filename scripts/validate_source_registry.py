"""Validate the tracked R0.2 source registry and collection field dictionary."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from travel_agent.data_governance import (  # noqa: E402
    SourceRegistryError,
    canonical_json_sha256,
    load_json_object,
    validate_governance_bundle,
)


def main() -> int:
    parser = argparse.ArgumentParser()
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

    registry = load_json_object(_rooted(args.registry))
    field_dictionary = load_json_object(_rooted(args.field_dictionary))
    try:
        validate_governance_bundle(registry, field_dictionary)
    except SourceRegistryError as exc:
        print(f"source governance validation failed: {exc}", file=sys.stderr)
        return 1

    decisions = Counter(source["decision"] for source in registry["sources"])
    summary = {
        "status": "valid",
        "registry_id": registry["registry_id"],
        "registry_sha256": canonical_json_sha256(registry),
        "field_dictionary_id": field_dictionary["dictionary_id"],
        "field_dictionary_sha256": canonical_json_sha256(field_dictionary),
        "source_count": len(registry["sources"]),
        "field_count": len(field_dictionary["fields"]),
        "exclusion_count": len(registry["exclusions"]),
        "decision_counts": dict(sorted(decisions.items())),
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
