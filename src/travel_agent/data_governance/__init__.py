"""Versioned source-governance primitives for research data."""

from .candidate_catalog import (
    CANDIDATE_CATALOG_SCHEMA_VERSION,
    CANDIDATE_COVERAGE_SCHEMA_VERSION,
    CandidateCatalogError,
    build_candidate_coverage,
    validate_candidate_catalog,
    validate_candidate_coverage,
)
from .source_registry import (
    FIELD_DICTIONARY_SCHEMA_VERSION,
    SOURCE_REGISTRY_SCHEMA_VERSION,
    SourceRegistryError,
    SourceUseDecision,
    canonical_json_sha256,
    evaluate_source_use,
    load_json_object,
    validate_governance_bundle,
)

__all__ = [
    "CANDIDATE_CATALOG_SCHEMA_VERSION",
    "CANDIDATE_COVERAGE_SCHEMA_VERSION",
    "FIELD_DICTIONARY_SCHEMA_VERSION",
    "SOURCE_REGISTRY_SCHEMA_VERSION",
    "CandidateCatalogError",
    "SourceRegistryError",
    "SourceUseDecision",
    "build_candidate_coverage",
    "canonical_json_sha256",
    "evaluate_source_use",
    "load_json_object",
    "validate_candidate_catalog",
    "validate_candidate_coverage",
    "validate_governance_bundle",
]
