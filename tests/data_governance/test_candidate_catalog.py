"""Candidate catalog tests. Traceability: G7-R0.2-04, ADR-0018."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from travel_agent.data_governance import (
    CandidateCatalogError,
    build_candidate_coverage,
    canonical_json_sha256,
    load_json_object,
    validate_candidate_catalog,
    validate_candidate_coverage,
)

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = ROOT / "data/governance/hangzhou-candidate-catalog-v1.json"
COVERAGE_PATH = ROOT / "data/governance/hangzhou-candidate-coverage-v1.json"
REGISTRY_PATH = ROOT / "data/governance/hangzhou-source-registry-v1.json"
DICTIONARY_PATH = ROOT / "data/governance/place-collection-field-dictionary-v1.json"


def _assets() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        load_json_object(CATALOG_PATH),
        load_json_object(COVERAGE_PATH),
        load_json_object(REGISTRY_PATH),
        load_json_object(DICTIONARY_PATH),
    )


def test_tracked_candidate_catalog_is_valid_versioned_and_candidate_only() -> None:
    catalog, coverage, registry, dictionary = _assets()

    validate_candidate_catalog(catalog, registry, dictionary)
    validate_candidate_coverage(coverage, catalog)

    assert catalog["status"] == "candidate"
    assert {item["review_state"] for item in catalog["candidates"]} == {"candidate"}
    assert len(catalog["candidates"]) == 72
    assert len(catalog["relation_clues"]) == 15
    assert canonical_json_sha256(catalog) == (
        "baba75143ededa9699bf8860e7841bd2e11e8d2a495060aee8d94bdab18237ba"
    )
    assert canonical_json_sha256(coverage) == (
        "14b495a79eb6f58a70197892c78aa9e0b674bc2b9350d10a544aac4d4915c881"
    )


def test_candidate_coverage_satisfies_r0_2_04_exit_thresholds() -> None:
    catalog, coverage, _, _ = _assets()

    assert coverage == build_candidate_coverage(catalog)
    assert coverage["exit_evaluation"]["status"] == "passed"
    assert coverage["actuals"] == {
        "candidate_count": 72,
        "travel_region_count": 11,
        "primary_category_count": 9,
        "night_or_fixed_time_count": 18,
        "indoor_or_rain_count": 28,
        "relation_clue_count": 15,
        "non_point_candidate_count": 24,
    }


def test_candidate_catalog_rejects_review_stage_escalation() -> None:
    catalog, _, registry, dictionary = _assets()
    catalog["status"] = "published"
    catalog["candidates"][0]["review_state"] = "human_verified"

    with pytest.raises(CandidateCatalogError) as exc_info:
        validate_candidate_catalog(catalog, registry, dictionary)

    message = str(exc_info.value)
    assert "status must be candidate" in message
    assert "review_state must be candidate" in message


def test_candidate_catalog_rejects_duplicate_poi_and_broken_relation() -> None:
    catalog, _, registry, dictionary = _assets()
    catalog["candidates"][1]["provider_candidate"]["poi_id"] = catalog["candidates"][0][
        "provider_candidate"
    ]["poi_id"]
    catalog["relation_clues"][0]["right_candidate_id"] = "hz-cand-missing"

    with pytest.raises(CandidateCatalogError) as exc_info:
        validate_candidate_catalog(catalog, registry, dictionary)

    message = str(exc_info.value)
    assert "duplicate provider poi_id" in message
    assert "references an unknown candidate" in message


def test_candidate_catalog_rejects_source_binding_drift() -> None:
    catalog, _, registry, dictionary = _assets()
    changed_registry = deepcopy(registry)
    changed_registry["limitations"].append("new policy text requires a new catalog version")

    with pytest.raises(CandidateCatalogError, match="registry_sha256 mismatch"):
        validate_candidate_catalog(catalog, changed_registry, dictionary)


def test_candidate_coverage_rejects_manual_summary_edit() -> None:
    catalog, coverage, _, _ = _assets()
    coverage["actuals"]["candidate_count"] += 1

    with pytest.raises(CandidateCatalogError, match="does not match catalog projection"):
        validate_candidate_coverage(coverage, catalog)


def test_candidate_catalog_cli_emits_non_sensitive_summary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_candidate_catalog.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout)

    assert summary["status"] == "valid"
    assert summary["candidate_count"] == 72
    assert summary["exit_evaluation"] == "passed"
    assert "key" not in result.stdout.lower()
    assert "password" not in result.stdout.lower()
