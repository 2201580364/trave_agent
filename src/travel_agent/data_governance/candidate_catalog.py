"""Validation and coverage derivation for the R0.2-04 candidate catalog."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .source_registry import (
    canonical_json_sha256,
    evaluate_source_use,
    validate_governance_bundle,
)

CANDIDATE_CATALOG_SCHEMA_VERSION = "hangzhou-candidate-catalog-v1"
CANDIDATE_COVERAGE_SCHEMA_VERSION = "hangzhou-candidate-coverage-v1"

PLACE_KINDS = frozenset(
    {
        "attraction",
        "scenic_area",
        "neighborhood",
        "walking_route",
        "market",
        "show",
        "experience",
    }
)
GEOMETRY_KINDS = frozenset({"point", "area", "route"})
PRIMARY_CATEGORIES = frozenset(
    {
        "自然山水",
        "古镇人文",
        "寺庙祈福",
        "城市观景",
        "博物馆",
        "美食街区",
        "网红打卡",
        "亲子乐园",
        "演出演艺",
    }
)
RELATION_TYPES = frozenset({"contains", "part_of", "overlaps", "same_experience"})
RELATION_REVIEW_STATUSES = frozenset({"unresolved"})
REQUIRED_PROVIDER_FIELDS = (
    "place.canonical_name",
    "place.admin_area",
    "place.address",
    "place.geometry_kind",
    "place.geometry",
    "external.gaode_poi_id",
)


class CandidateCatalogError(ValueError):
    """The tracked candidate catalog or its coverage matrix is invalid."""


def validate_candidate_catalog(
    catalog: dict[str, Any],
    registry: dict[str, Any],
    field_dictionary: dict[str, Any],
) -> None:
    """Fail closed when a candidate asset is ambiguous or crosses review stages."""

    validate_governance_bundle(registry, field_dictionary)
    errors: list[str] = []

    if catalog.get("schema_version") != CANDIDATE_CATALOG_SCHEMA_VERSION:
        errors.append("candidate catalog schema_version mismatch")
    if catalog.get("city_id") != "hangzhou":
        errors.append("candidate catalog city_id must be hangzhou")
    if catalog.get("status") != "candidate":
        errors.append("candidate catalog status must be candidate")

    source_binding = catalog.get("source_registry")
    if not isinstance(source_binding, dict):
        errors.append("candidate catalog requires source_registry binding")
    else:
        if source_binding.get("registry_id") != registry.get("registry_id"):
            errors.append("candidate catalog registry_id mismatch")
        if source_binding.get("registry_sha256") != canonical_json_sha256(registry):
            errors.append("candidate catalog registry_sha256 mismatch")

    dictionary_binding = catalog.get("field_dictionary")
    if not isinstance(dictionary_binding, dict):
        errors.append("candidate catalog requires field_dictionary binding")
    else:
        if dictionary_binding.get("dictionary_id") != field_dictionary.get("dictionary_id"):
            errors.append("candidate catalog dictionary_id mismatch")
        if dictionary_binding.get("dictionary_sha256") != canonical_json_sha256(
            field_dictionary
        ):
            errors.append("candidate catalog dictionary_sha256 mismatch")

    candidates = catalog.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidate catalog requires candidates")
        candidates = []

    candidate_ids: set[str] = set()
    poi_ids: set[str] = set()
    for index, candidate in enumerate(candidates):
        _validate_candidate(
            candidate,
            index=index,
            registry=registry,
            field_dictionary=field_dictionary,
            candidate_ids=candidate_ids,
            poi_ids=poi_ids,
            errors=errors,
        )

    relation_clues = catalog.get("relation_clues")
    if not isinstance(relation_clues, list):
        errors.append("candidate catalog requires relation_clues")
        relation_clues = []
    relation_ids: set[str] = set()
    for index, relation in enumerate(relation_clues):
        _validate_relation_clue(
            relation,
            index=index,
            candidate_ids=candidate_ids,
            relation_ids=relation_ids,
            errors=errors,
        )

    if errors:
        raise CandidateCatalogError("; ".join(errors))


def build_candidate_coverage(catalog: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic coverage matrix from a validated catalog payload."""

    candidates = catalog["candidates"]
    region_counts = Counter(item["travel_region_id"] for item in candidates)
    category_counts = Counter(item["primary_category"] for item in candidates)
    kind_counts = Counter(item["place_kind_candidate"] for item in candidates)
    geometry_counts = Counter(item["geometry_kind_candidate"] for item in candidates)
    night_ids = sorted(
        item["candidate_id"] for item in candidates if item["coverage"]["night_or_fixed_time"]
    )
    rain_ids = sorted(
        item["candidate_id"] for item in candidates if item["coverage"]["indoor_or_rain"]
    )
    non_point_ids = sorted(
        item["candidate_id"] for item in candidates if item["geometry_kind_candidate"] != "point"
    )

    thresholds = {
        "candidate_count_min": 50,
        "travel_region_count_min": 8,
        "primary_category_count_min": 8,
        "night_or_fixed_time_count_min": 8,
        "indoor_or_rain_count_min": 5,
        "relation_clue_count_min": 1,
    }
    actuals = {
        "candidate_count": len(candidates),
        "travel_region_count": len(region_counts),
        "primary_category_count": len(category_counts),
        "night_or_fixed_time_count": len(night_ids),
        "indoor_or_rain_count": len(rain_ids),
        "relation_clue_count": len(catalog["relation_clues"]),
        "non_point_candidate_count": len(non_point_ids),
    }
    checks = [
        {
            "check_id": key.removesuffix("_min"),
            "required_min": required,
            "actual": actuals[key.removesuffix("_min")],
            "passed": actuals[key.removesuffix("_min")] >= required,
        }
        for key, required in thresholds.items()
    ]

    return {
        "schema_version": CANDIDATE_COVERAGE_SCHEMA_VERSION,
        "coverage_id": "hangzhou-m1-candidate-coverage-v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": canonical_json_sha256(catalog),
        "status": "candidate",
        "generated_at": catalog["generated_at"],
        "thresholds": thresholds,
        "actuals": actuals,
        "exit_evaluation": {
            "status": "passed" if all(check["passed"] for check in checks) else "failed",
            "checks": checks,
        },
        "dimensions": {
            "travel_regions": _counter_rows(region_counts, "travel_region_id"),
            "primary_categories": _counter_rows(category_counts, "primary_category"),
            "place_kinds": _counter_rows(kind_counts, "place_kind"),
            "geometry_kinds": _counter_rows(geometry_counts, "geometry_kind"),
            "night_or_fixed_time_candidate_ids": night_ids,
            "indoor_or_rain_candidate_ids": rain_ids,
            "non_point_candidate_ids": non_point_ids,
        },
        "limitations": [
            "覆盖通过只表示候选发现达到R0.2-04工程门槛，不表示地点事实已人工审核。",
            "高德POI坐标是候选定位，不是human_verified到达或离开访问点。",
            "未裁决关系线索必须在R0.2-05审核工作台中形成明确裁决。",
        ],
    }


def validate_candidate_coverage(
    coverage: dict[str, Any],
    catalog: dict[str, Any],
) -> None:
    """Ensure a tracked matrix is the exact deterministic projection of its catalog."""

    expected = build_candidate_coverage(catalog)
    if coverage != expected:
        raise CandidateCatalogError("candidate coverage does not match catalog projection")
    if coverage["exit_evaluation"]["status"] != "passed":
        raise CandidateCatalogError("candidate coverage thresholds are not satisfied")


def _validate_candidate(
    candidate: Any,
    *,
    index: int,
    registry: dict[str, Any],
    field_dictionary: dict[str, Any],
    candidate_ids: set[str],
    poi_ids: set[str],
    errors: list[str],
) -> None:
    prefix = f"candidate[{index}]"
    if not isinstance(candidate, dict):
        errors.append(f"{prefix} must be an object")
        return
    candidate_id = candidate.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.startswith("hz-cand-"):
        errors.append(f"{prefix} has invalid candidate_id")
    elif candidate_id in candidate_ids:
        errors.append(f"duplicate candidate_id {candidate_id}")
    else:
        candidate_ids.add(candidate_id)

    if candidate.get("review_state") != "candidate":
        errors.append(f"{prefix} review_state must be candidate")
    if candidate.get("place_kind_candidate") not in PLACE_KINDS:
        errors.append(f"{prefix} has invalid place_kind_candidate")
    if candidate.get("geometry_kind_candidate") not in GEOMETRY_KINDS:
        errors.append(f"{prefix} has invalid geometry_kind_candidate")
    if candidate.get("primary_category") not in PRIMARY_CATEGORIES:
        errors.append(f"{prefix} has invalid primary_category")
    for key in ("canonical_name_candidate", "travel_region_id"):
        if not isinstance(candidate.get(key), str) or not candidate[key].strip():
            errors.append(f"{prefix} requires {key}")

    coverage = candidate.get("coverage")
    if not isinstance(coverage, dict):
        errors.append(f"{prefix} requires coverage")
    else:
        for key in ("night_or_fixed_time", "indoor_or_rain"):
            if not isinstance(coverage.get(key), bool):
                errors.append(f"{prefix} coverage.{key} must be boolean")
        for key in ("audiences", "suitable_periods"):
            value = coverage.get(key)
            if not isinstance(value, list) or not value or any(
                not isinstance(item, str) or not item for item in value
            ):
                errors.append(f"{prefix} coverage.{key} requires strings")

    provider = candidate.get("provider_candidate")
    if not isinstance(provider, dict):
        errors.append(f"{prefix} requires provider_candidate")
        return
    if provider.get("source_id") != "gaode-web-service":
        errors.append(f"{prefix} provider source must be gaode-web-service")
    if provider.get("collection_mode") != "api":
        errors.append(f"{prefix} provider collection_mode must be api")
    poi_id = provider.get("poi_id")
    if not isinstance(poi_id, str) or not poi_id:
        errors.append(f"{prefix} requires provider poi_id")
    elif poi_id in poi_ids:
        errors.append(f"duplicate provider poi_id {poi_id}")
    else:
        poi_ids.add(poi_id)
    for key in ("name", "observed_at"):
        if not isinstance(provider.get(key), str) or not provider[key].strip():
            errors.append(f"{prefix} provider requires {key}")
    location = provider.get("location")
    if not isinstance(location, dict):
        errors.append(f"{prefix} provider requires location")
    else:
        lng = location.get("lng")
        lat = location.get("lat")
        if not isinstance(lng, int | float) or not 118.5 <= lng <= 121.0:
            errors.append(f"{prefix} provider lng outside Hangzhou envelope")
        if not isinstance(lat, int | float) or not 29.0 <= lat <= 31.5:
            errors.append(f"{prefix} provider lat outside Hangzhou envelope")

    flags = candidate.get("review_flags")
    if not isinstance(flags, list) or not {
        "ACCESS_POINT_UNVERIFIED",
        "TIME_RULES_NOT_COLLECTED",
    } <= set(flags):
        errors.append(f"{prefix} must retain candidate review flags")

    for field_id in REQUIRED_PROVIDER_FIELDS:
        decision = evaluate_source_use(
            registry,
            field_dictionary,
            source_id="gaode-web-service",
            field_id=field_id,
            collection_mode="api",
            target_stage="staging",
        )
        if not decision.allowed:
            errors.append(f"{prefix} source use denied for {field_id}: {decision.reason_code}")


def _validate_relation_clue(
    relation: Any,
    *,
    index: int,
    candidate_ids: set[str],
    relation_ids: set[str],
    errors: list[str],
) -> None:
    prefix = f"relation_clue[{index}]"
    if not isinstance(relation, dict):
        errors.append(f"{prefix} must be an object")
        return
    clue_id = relation.get("clue_id")
    if not isinstance(clue_id, str) or not clue_id.startswith("hz-rel-"):
        errors.append(f"{prefix} has invalid clue_id")
    elif clue_id in relation_ids:
        errors.append(f"duplicate relation clue {clue_id}")
    else:
        relation_ids.add(clue_id)
    if relation.get("relation_candidate") not in RELATION_TYPES:
        errors.append(f"{prefix} has invalid relation_candidate")
    if relation.get("review_status") not in RELATION_REVIEW_STATUSES:
        errors.append(f"{prefix} review_status must be unresolved")
    left = relation.get("left_candidate_id")
    right = relation.get("right_candidate_id")
    if left not in candidate_ids or right not in candidate_ids:
        errors.append(f"{prefix} references an unknown candidate")
    if left == right:
        errors.append(f"{prefix} cannot relate a candidate to itself")
    if not isinstance(relation.get("reason_code"), str) or not relation["reason_code"]:
        errors.append(f"{prefix} requires reason_code")


def _counter_rows(counter: Counter[str], key: str) -> list[dict[str, Any]]:
    return [{key: value, "candidate_count": counter[value]} for value in sorted(counter)]
