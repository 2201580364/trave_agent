"""Application commands for plan sharing and reference-copy flow."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CreatePlanShare:
    principal_id: str
    plan_share_intent_id: str
    trip_id: str
    revision_id: str
    template: str = "simple"


@dataclass(frozen=True, slots=True)
class CopyPlanShareToDraft:
    principal_id: str
    public_token: str
