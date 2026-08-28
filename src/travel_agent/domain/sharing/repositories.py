"""Repository contract for M1 plan shares."""

from __future__ import annotations

from typing import Protocol

from .entities import PlanShare


class PlanShareRepository(Protocol):
    def get(self, plan_share_id: str) -> PlanShare | None: ...

    def get_by_intent(self, plan_share_intent_id: str) -> PlanShare | None: ...

    def get_by_public_token_hash(self, public_token_hash: str) -> PlanShare | None: ...

    def add(self, share: PlanShare) -> None: ...
