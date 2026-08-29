"""Fail-closed validation for source registries and collection field dictionaries."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

SOURCE_REGISTRY_SCHEMA_VERSION = "source-registry-v1"
FIELD_DICTIONARY_SCHEMA_VERSION = "place-collection-field-dictionary-v1"

SOURCE_DECISIONS = frozenset({"approved", "conditional", "pending_review", "prohibited"})
SOURCE_REVIEW_STATUSES = frozenset(
    {"reviewed", "pending_browser_review", "prohibited_by_policy"}
)
SOURCE_KINDS = frozenset(
    {
        "government_public_site",
        "official_operator_site",
        "open_data_portal",
        "licensed_api",
        "editorial_public_page",
    }
)
SOURCE_ROLES = frozenset(
    {
        "government",
        "official_operator",
        "licensed_open_data",
        "licensed_map_provider",
        "licensed_weather_provider",
        "curated_editorial",
    }
)
COLLECTION_MODES = frozenset(
    {"api", "dataset_download", "manual_reference", "public_page_fetch"}
)
TARGET_STAGES = frozenset({"staging", "published"})
FIELD_FACT_CLASSES = frozenset(
    {"provenance", "hard_fact", "reviewed_attribute", "soft_signal", "provider_fact"}
)
PUBLISH_REQUIREMENTS = frozenset(
    {"required", "human_verified", "curated_review", "provider_verified"}
)
RAW_RETENTION_POLICIES = frozenset(
    {"none", "metadata_and_hash_only", "contract_limited_cache"}
)
CREDENTIAL_POLICIES = frozenset({"none", "environment_only"})
ATTRIBUTION_POLICIES = frozenset(
    {"source_url_and_observed_at", "dataset_specific", "provider_terms"}
)
EVIDENCE_KINDS = frozenset(
    {"homepage", "documentation", "terms", "restriction", "attribution", "robots"}
)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.-]{2,79}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ISO_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SENSITIVE_TEXT = re.compile(
    r"(?i)(?:api[_-]?key|password|secret|token)\s*[=:]\s*[^<\s]+|"
    r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY|"
    r"(?:mysql|redis)(?:\+[^:]*)?://[^\s:/]+:[^\s@]+@"
)


class SourceRegistryError(ValueError):
    """The source-governance bundle is invalid or cannot authorize collection."""


@dataclass(frozen=True)
class SourceUseDecision:
    """A stable allow/deny result for one source, field, mode and target stage."""

    allowed: bool
    reason_code: str
    source_id: str
    field_id: str
    collection_mode: str
    target_stage: str


def load_json_object(path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object without accepting arrays or scalar roots."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SourceRegistryError(f"{path} must contain a JSON object")
    return payload


def canonical_json_sha256(payload: dict[str, Any]) -> str:
    """Hash a JSON object after stable canonical serialization."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_governance_bundle(
    registry: dict[str, Any],
    field_dictionary: dict[str, Any],
) -> None:
    """Validate schema, permissions and fail-closed publication rules."""

    errors: list[str] = []
    _validate_field_dictionary(field_dictionary, errors)
    field_index = _index_by_id(field_dictionary.get("fields"), "field_id", "fields", errors)
    _validate_registry(registry, field_index, errors)
    if errors:
        raise SourceRegistryError("; ".join(errors))


def evaluate_source_use(
    registry: dict[str, Any],
    field_dictionary: dict[str, Any],
    *,
    source_id: str,
    field_id: str,
    collection_mode: str,
    target_stage: Literal["staging", "published"],
) -> SourceUseDecision:
    """Evaluate source use; conditional sources may enter staging but never publish."""

    validate_governance_bundle(registry, field_dictionary)
    sources = _index_by_id(registry["sources"], "source_id", "sources", [])
    fields = _index_by_id(field_dictionary["fields"], "field_id", "fields", [])

    source = sources.get(source_id)
    if source is None:
        return _decision(
            False, "SOURCE_NOT_REGISTERED", source_id, field_id, collection_mode, target_stage
        )
    field = fields.get(field_id)
    if field is None:
        return _decision(
            False, "FIELD_NOT_REGISTERED", source_id, field_id, collection_mode, target_stage
        )
    if collection_mode not in COLLECTION_MODES:
        return _decision(
            False, "COLLECTION_MODE_UNKNOWN", source_id, field_id, collection_mode, target_stage
        )
    if target_stage not in TARGET_STAGES:
        return _decision(
            False, "TARGET_STAGE_UNKNOWN", source_id, field_id, collection_mode, target_stage
        )

    decision = source["decision"]
    if decision == "prohibited":
        return _decision(
            False, "SOURCE_PROHIBITED", source_id, field_id, collection_mode, target_stage
        )
    if decision == "pending_review":
        return _decision(
            False, "SOURCE_REVIEW_PENDING", source_id, field_id, collection_mode, target_stage
        )
    if collection_mode not in source["collection_modes"]:
        return _decision(
            False,
            "COLLECTION_MODE_NOT_ALLOWED",
            source_id,
            field_id,
            collection_mode,
            target_stage,
        )
    if field_id not in source["allowed_fields"]:
        return _decision(
            False,
            "FIELD_NOT_ALLOWED_FOR_SOURCE",
            source_id,
            field_id,
            collection_mode,
            target_stage,
        )
    if collection_mode not in field["allowed_collection_modes"]:
        return _decision(
            False,
            "COLLECTION_MODE_NOT_ALLOWED_FOR_FIELD",
            source_id,
            field_id,
            collection_mode,
            target_stage,
        )
    if not set(source["roles"]).intersection(field["allowed_source_roles"]):
        return _decision(
            False,
            "SOURCE_ROLE_NOT_ALLOWED_FOR_FIELD",
            source_id,
            field_id,
            collection_mode,
            target_stage,
        )
    if target_stage == "published" and decision != "approved":
        return _decision(
            False,
            "CONDITIONAL_SOURCE_STAGING_ONLY",
            source_id,
            field_id,
            collection_mode,
            target_stage,
        )

    reason = (
        "SOURCE_USE_APPROVED"
        if target_stage == "published"
        else "SOURCE_USE_ALLOWED_FOR_STAGING"
    )
    return _decision(True, reason, source_id, field_id, collection_mode, target_stage)


def _decision(
    allowed: bool,
    reason_code: str,
    source_id: str,
    field_id: str,
    collection_mode: str,
    target_stage: str,
) -> SourceUseDecision:
    return SourceUseDecision(
        allowed=allowed,
        reason_code=reason_code,
        source_id=source_id,
        field_id=field_id,
        collection_mode=collection_mode,
        target_stage=target_stage,
    )


def _validate_field_dictionary(payload: dict[str, Any], errors: list[str]) -> None:
    if payload.get("schema_version") != FIELD_DICTIONARY_SCHEMA_VERSION:
        errors.append("field dictionary schema_version mismatch")
    _require_identifier(payload, "dictionary_id", "field dictionary", errors)
    _require_iso_datetime(payload, "generated_at", "field dictionary", errors)
    fields = payload.get("fields")
    field_index = _index_by_id(fields, "field_id", "fields", errors)
    if not field_index:
        errors.append("field dictionary must contain fields")
        return
    for field_id, field in field_index.items():
        prefix = f"field {field_id}"
        if field.get("fact_class") not in FIELD_FACT_CLASSES:
            errors.append(f"{prefix} has invalid fact_class")
        if field.get("publish_requirement") not in PUBLISH_REQUIREMENTS:
            errors.append(f"{prefix} has invalid publish_requirement")
        if field.get("pii_allowed") is not False:
            errors.append(f"{prefix} must set pii_allowed=false")
        _require_nonempty_string_list(field, "allowed_source_roles", prefix, errors)
        _require_nonempty_string_list(field, "allowed_collection_modes", prefix, errors)
        for role in field.get("allowed_source_roles", []):
            if role not in SOURCE_ROLES:
                errors.append(f"{prefix} has unknown source role {role}")
        for mode in field.get("allowed_collection_modes", []):
            if mode not in COLLECTION_MODES:
                errors.append(f"{prefix} has unknown collection mode {mode}")
        if (
            not isinstance(field.get("collection_rule"), str)
            or not field["collection_rule"].strip()
        ):
            errors.append(f"{prefix} requires collection_rule")
        if not isinstance(field.get("publish_rule"), str) or not field["publish_rule"].strip():
            errors.append(f"{prefix} requires publish_rule")


def _validate_registry(
    payload: dict[str, Any],
    field_index: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    if payload.get("schema_version") != SOURCE_REGISTRY_SCHEMA_VERSION:
        errors.append("source registry schema_version mismatch")
    _require_identifier(payload, "registry_id", "source registry", errors)
    _require_identifier(payload, "city_id", "source registry", errors)
    _require_iso_datetime(payload, "reviewed_at", "source registry", errors)
    if _contains_sensitive_text(payload):
        errors.append("source registry contains sensitive credential text")

    sources = payload.get("sources")
    source_index = _index_by_id(sources, "source_id", "sources", errors)
    if not source_index:
        errors.append("source registry must contain sources")
    for source_id, source in source_index.items():
        _validate_source(source_id, source, field_index, errors)
    _validate_exclusions(payload.get("exclusions"), errors)


def _validate_source(
    source_id: str,
    source: dict[str, Any],
    field_index: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    prefix = f"source {source_id}"
    decision = source.get("decision")
    if decision not in SOURCE_DECISIONS:
        errors.append(f"{prefix} has invalid decision")
    if source.get("review_status") not in SOURCE_REVIEW_STATUSES:
        errors.append(f"{prefix} has invalid review_status")
    if source.get("source_kind") not in SOURCE_KINDS:
        errors.append(f"{prefix} has invalid source_kind")
    if source.get("raw_retention") not in RAW_RETENTION_POLICIES:
        errors.append(f"{prefix} has invalid raw_retention")
    if source.get("credential_policy") not in CREDENTIAL_POLICIES:
        errors.append(f"{prefix} has invalid credential_policy")
    if source.get("attribution_policy") not in ATTRIBUTION_POLICIES:
        errors.append(f"{prefix} has invalid attribution_policy")
    _require_iso_datetime(source, "reviewed_at", prefix, errors)
    _require_iso_date(source, "next_review_on", prefix, errors)
    _require_nonempty_string_list(source, "roles", prefix, errors)
    for role in source.get("roles", []):
        if role not in SOURCE_ROLES:
            errors.append(f"{prefix} has unknown role {role}")

    base_urls = source.get("base_urls")
    if not isinstance(base_urls, list) or not base_urls:
        errors.append(f"{prefix} requires base_urls")
    else:
        for url in base_urls:
            if not _is_https_url(url):
                errors.append(f"{prefix} has non-HTTPS or invalid base URL")

    modes = source.get("collection_modes")
    allowed_fields = source.get("allowed_fields")
    prohibited_fields = source.get("prohibited_fields")
    if not isinstance(modes, list) or any(mode not in COLLECTION_MODES for mode in modes):
        errors.append(f"{prefix} has invalid collection_modes")
        modes = []
    if not isinstance(allowed_fields, list) or any(
        not isinstance(item, str) for item in allowed_fields
    ):
        errors.append(f"{prefix} has invalid allowed_fields")
        allowed_fields = []
    if not isinstance(prohibited_fields, list) or any(
        not isinstance(item, str) for item in prohibited_fields
    ):
        errors.append(f"{prefix} has invalid prohibited_fields")
        prohibited_fields = []
    unknown_fields = sorted(set(allowed_fields).difference(field_index))
    if unknown_fields:
        errors.append(f"{prefix} references unknown fields {unknown_fields}")
    if set(allowed_fields).intersection(prohibited_fields):
        errors.append(f"{prefix} allows and prohibits the same field")

    conditions = source.get("conditions")
    if not isinstance(conditions, list) or any(not isinstance(item, str) for item in conditions):
        errors.append(f"{prefix} has invalid conditions")
        conditions = []
    if decision == "conditional" and not conditions:
        errors.append(f"{prefix} conditional decision requires conditions")
    if decision in {"pending_review", "prohibited"} and (modes or allowed_fields):
        errors.append(f"{prefix} pending/prohibited sources must fail closed")
    if decision == "approved" and source.get("review_status") != "reviewed":
        errors.append(f"{prefix} approved source must be reviewed")
    if decision in {"approved", "conditional"}:
        evidence = source.get("terms_evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix} requires terms_evidence")
        else:
            for index, item in enumerate(evidence):
                _validate_evidence(item, f"{prefix} evidence[{index}]", errors)


def _validate_evidence(value: Any, prefix: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{prefix} must be an object")
        return
    if value.get("kind") not in EVIDENCE_KINDS:
        errors.append(f"{prefix} has invalid kind")
    if not _is_https_url(value.get("url")):
        errors.append(f"{prefix} has invalid URL")
    _require_iso_datetime(value, "checked_at", prefix, errors)
    status = value.get("http_status")
    if not isinstance(status, int) or status < 100 or status > 599:
        errors.append(f"{prefix} has invalid http_status")
    digest = value.get("content_sha256")
    if digest is not None and (not isinstance(digest, str) or _SHA256.fullmatch(digest) is None):
        errors.append(f"{prefix} has invalid content_sha256")


def _validate_exclusions(value: Any, errors: list[str]) -> None:
    index = _index_by_id(value, "exclusion_id", "exclusions", errors)
    if not index:
        errors.append("source registry must contain an exclusion list")
        return
    for exclusion_id, exclusion in index.items():
        prefix = f"exclusion {exclusion_id}"
        if not isinstance(exclusion.get("host_patterns"), list) or not exclusion["host_patterns"]:
            errors.append(f"{prefix} requires host_patterns")
        if not isinstance(exclusion.get("reason_code"), str) or not exclusion["reason_code"]:
            errors.append(f"{prefix} requires reason_code")
        modes = exclusion.get("prohibited_collection_modes")
        if not isinstance(modes, list) or not modes:
            errors.append(f"{prefix} requires prohibited_collection_modes")
        elif any(mode not in COLLECTION_MODES for mode in modes):
            errors.append(f"{prefix} has unknown prohibited collection mode")
        content = exclusion.get("prohibited_content")
        if not isinstance(content, list) or not content:
            errors.append(f"{prefix} requires prohibited_content")
        if not isinstance(exclusion.get("reconsideration_trigger"), str) or not exclusion[
            "reconsideration_trigger"
        ].strip():
            errors.append(f"{prefix} requires reconsideration_trigger")


def _index_by_id(
    value: Any,
    id_key: str,
    label: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        identifier = item.get(id_key)
        if not isinstance(identifier, str) or _IDENTIFIER.fullmatch(identifier) is None:
            errors.append(f"{label}[{index}] has invalid {id_key}")
            continue
        if identifier in result:
            errors.append(f"{label} contains duplicate {id_key} {identifier}")
            continue
        result[identifier] = item
    return result


def _require_identifier(
    payload: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        errors.append(f"{prefix} has invalid {key}")


def _require_iso_datetime(
    payload: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or _ISO_DATETIME.fullmatch(value) is None:
        errors.append(f"{prefix} has invalid {key}")


def _require_iso_date(
    payload: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = payload.get(key)
    if not isinstance(value, str) or _ISO_DATE.fullmatch(value) is None:
        errors.append(f"{prefix} has invalid {key}")


def _require_nonempty_string_list(
    payload: dict[str, Any], key: str, prefix: str, errors: list[str]
) -> None:
    value = payload.get(key)
    if not isinstance(value, list) or not value or any(not isinstance(item, str) for item in value):
        errors.append(f"{prefix} requires non-empty string list {key}")


def _is_https_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.username is None


def _contains_sensitive_text(payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return _SENSITIVE_TEXT.search(serialized) is not None
