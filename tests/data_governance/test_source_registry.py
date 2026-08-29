"""Source-governance tests. Traceability: G7-R0.2-02, ADR-0018."""

from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from travel_agent.data_governance import (
    SourceRegistryError,
    canonical_json_sha256,
    evaluate_source_use,
    load_json_object,
    validate_governance_bundle,
)

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / "data" / "governance" / "hangzhou-source-registry-v1.json"
DICTIONARY_PATH = (
    ROOT / "data" / "governance" / "place-collection-field-dictionary-v1.json"
)


def _bundle() -> tuple[dict[str, Any], dict[str, Any]]:
    return load_json_object(REGISTRY_PATH), load_json_object(DICTIONARY_PATH)


def test_tracked_governance_bundle_is_valid_and_versioned() -> None:
    registry, dictionary = _bundle()

    validate_governance_bundle(registry, dictionary)

    assert len(registry["sources"]) == 5
    assert len(registry["exclusions"]) == 2
    assert len(dictionary["fields"]) == 58
    assert canonical_json_sha256(registry) == (
        "c0085129bbca7a38c963985a8c29ef7b857275d8ff833b53cca9b6207470d21a"
    )
    assert canonical_json_sha256(dictionary) == (
        "773a7db58357b0cda5a7f9fa1fbd6a1e3d7351288e7601bbd0196d084ee7ed3a"
    )


def test_approved_provider_field_can_reach_published() -> None:
    registry, dictionary = _bundle()

    decision = evaluate_source_use(
        registry,
        dictionary,
        source_id="gaode-web-service",
        field_id="od.duration_min",
        collection_mode="api",
        target_stage="published",
    )

    assert decision.allowed is True
    assert decision.reason_code == "SOURCE_USE_APPROVED"


def test_conditional_government_source_is_staging_only() -> None:
    registry, dictionary = _bundle()
    conditional_sources = [
        source for source in registry["sources"] if source["decision"] == "conditional"
    ]

    staging = evaluate_source_use(
        registry,
        dictionary,
        source_id="hangzhou-wgly-public-web",
        field_id="time.rules",
        collection_mode="manual_reference",
        target_stage="staging",
    )
    published = evaluate_source_use(
        registry,
        dictionary,
        source_id="hangzhou-wgly-public-web",
        field_id="time.rules",
        collection_mode="manual_reference",
        target_stage="published",
    )

    assert staging.allowed is True
    assert staging.reason_code == "SOURCE_USE_ALLOWED_FOR_STAGING"
    assert published.allowed is False
    assert published.reason_code == "CONDITIONAL_SOURCE_STAGING_ONLY"
    assert {source["review_status"] for source in conditional_sources} == {"reviewed"}


def test_source_and_field_collection_modes_are_both_enforced() -> None:
    registry, dictionary = _bundle()

    source_denied = evaluate_source_use(
        registry,
        dictionary,
        source_id="gaode-web-service",
        field_id="place.canonical_name",
        collection_mode="manual_reference",
        target_stage="staging",
    )
    field_denied = evaluate_source_use(
        registry,
        dictionary,
        source_id="hangzhou-wgly-public-web",
        field_id="provenance.content_sha256",
        collection_mode="manual_reference",
        target_stage="staging",
    )

    assert source_denied.reason_code == "COLLECTION_MODE_NOT_ALLOWED"
    assert field_denied.reason_code == "COLLECTION_MODE_NOT_ALLOWED_FOR_FIELD"


def test_unregistered_source_or_field_fails_closed() -> None:
    registry, dictionary = _bundle()

    missing_source = evaluate_source_use(
        registry,
        dictionary,
        source_id="unknown-source",
        field_id="place.canonical_name",
        collection_mode="manual_reference",
        target_stage="staging",
    )
    missing_field = evaluate_source_use(
        registry,
        dictionary,
        source_id="gaode-web-service",
        field_id="review.full_text",
        collection_mode="api",
        target_stage="staging",
    )

    assert missing_source.reason_code == "SOURCE_NOT_REGISTERED"
    assert missing_field.reason_code == "FIELD_NOT_REGISTERED"


def test_pending_source_cannot_keep_collection_permissions() -> None:
    registry, dictionary = _bundle()
    source = registry["sources"][0]
    source["decision"] = "pending_review"

    with pytest.raises(SourceRegistryError, match="must fail closed"):
        validate_governance_bundle(registry, dictionary)


def test_approved_source_requires_completed_review() -> None:
    registry, dictionary = _bundle()
    source = next(item for item in registry["sources"] if item["decision"] == "approved")
    source["review_status"] = "pending_browser_review"

    with pytest.raises(SourceRegistryError, match="approved source must be reviewed"):
        validate_governance_bundle(registry, dictionary)


def test_unknown_field_and_duplicate_source_are_rejected() -> None:
    registry, dictionary = _bundle()
    registry["sources"][0]["allowed_fields"].append("unknown.field")
    registry["sources"].append(deepcopy(registry["sources"][0]))

    with pytest.raises(SourceRegistryError) as exc_info:
        validate_governance_bundle(registry, dictionary)

    message = str(exc_info.value)
    assert "duplicate source_id" in message
    assert "references unknown fields" in message


def test_registry_rejects_credentials_and_full_connection_strings() -> None:
    registry, dictionary = _bundle()
    registry["limitations"].append("password=do-not-store-this")

    with pytest.raises(SourceRegistryError, match="sensitive credential text"):
        validate_governance_bundle(registry, dictionary)


def test_field_dictionary_forbids_pii_and_unknown_source_roles() -> None:
    registry, dictionary = _bundle()
    dictionary["fields"][0]["pii_allowed"] = True
    dictionary["fields"][0]["allowed_source_roles"].append("social_user")

    with pytest.raises(SourceRegistryError) as exc_info:
        validate_governance_bundle(registry, dictionary)

    message = str(exc_info.value)
    assert "pii_allowed=false" in message
    assert "unknown source role social_user" in message


def test_exclusion_list_covers_social_and_ota_bulk_collection() -> None:
    registry, _ = _bundle()
    patterns = {
        pattern
        for exclusion in registry["exclusions"]
        for pattern in exclusion["host_patterns"]
    }

    assert {"xiaohongshu.com", "douyin.com", "mp.weixin.qq.com"} <= patterns
    assert {"dianping.com", "ctrip.com", "mafengwo.cn"} <= patterns


def test_cli_emits_non_sensitive_machine_readable_summary() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_source_registry.py", "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout)

    assert summary["status"] == "valid"
    assert summary["source_count"] == 5
    assert summary["field_count"] == 58
    assert summary["decision_counts"] == {"approved": 2, "conditional": 3}
    assert "key" not in result.stdout.lower()
    assert "password" not in result.stdout.lower()
