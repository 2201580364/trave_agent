"""Persistence ports for structured feedback."""

from __future__ import annotations

from typing import Protocol

from .entities import Feedback


class FeedbackRepository(Protocol):
    def get(self, feedback_id: str) -> Feedback | None: ...

    def get_by_intent(self, feedback_intent_id: str) -> Feedback | None: ...

    def get_by_target(
        self,
        principal_id: str,
        revision_id: str,
        target_key: str,
    ) -> Feedback | None: ...

    def add(self, feedback: Feedback) -> None: ...
