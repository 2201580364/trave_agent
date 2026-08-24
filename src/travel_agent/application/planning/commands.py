"""Immutable command DTOs for planning write use cases."""

from __future__ import annotations

from dataclasses import dataclass

from travel_agent.domain.planning import TravelFacts, VisitPeriodPreferenceInput


@dataclass(frozen=True, slots=True)
class CreateDraft:
    principal_id: str
    city_id: str


@dataclass(frozen=True, slots=True)
class UpdateTravelFacts:
    principal_id: str
    draft_id: str
    expected_draft_version: int
    travel_facts: TravelFacts


@dataclass(frozen=True, slots=True)
class ReplaceAttractionSelection:
    principal_id: str
    draft_id: str
    expected_draft_version: int
    attraction_ids: tuple[str, ...]
    visit_period_preferences: tuple[VisitPeriodPreferenceInput, ...] = ()


@dataclass(frozen=True, slots=True)
class SubmitGeneration:
    principal_id: str
    generation_intent_id: str
    draft_id: str
    draft_version: int
