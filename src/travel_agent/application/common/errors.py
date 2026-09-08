"""Stable application errors independent of HTTP and persistence frameworks.

User copy for codes without structured details is centralized in
``application.admin.error_messages`` so both admin and user-facing clients
render consistent Chinese copy; clients must branch on ``code``, never on
``message`` (api-contract.md §2.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from travel_agent.application.common.error_messages import (
    admin_error_message,
    summarize_error_details,
)


@dataclass(eq=False)
class ApplicationError(Exception):
    code: str
    message: str
    details: dict[str, object] = field(default_factory=dict)
    retryable: bool = False

    def __str__(self) -> str:
        return self.message


class ResourceNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("resource_not_found", "资源不存在或无权访问。")


class DraftVersionConflictError(ApplicationError):
    def __init__(self, *, expected_version: int, current_version: int) -> None:
        super().__init__(
            "draft_version_conflict",
            admin_error_message("draft_version_conflict"),
            {
                "expected_version": expected_version,
                "current_version": current_version,
            },
        )


class GenerationIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "generation_intent_conflict",
            admin_error_message("generation_intent_conflict"),
        )


class DraftNotReadyError(ApplicationError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        details: dict[str, object] = {"issues": issues}
        super().__init__(
            "draft_not_ready",
            admin_error_message("draft_not_ready")
            + summarize_error_details("draft_not_ready", details),
            details,
        )


class InvalidStateTransitionError(ApplicationError):
    def __init__(self, message: str | None = None) -> None:
        fallback = admin_error_message("invalid_state_transition")
        super().__init__(
            "invalid_state_transition",
            message if message and _has_cjk(message) else fallback,
        )


class TripRevisionConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "trip_revision_conflict",
            admin_error_message("trip_revision_conflict"),
        )


class InvalidAttractionReplacementError(ApplicationError):
    def __init__(self, message: str | None = None) -> None:
        fallback = admin_error_message("invalid_attraction_replacement")
        super().__init__(
            "invalid_attraction_replacement",
            message if message and _has_cjk(message) else fallback,
        )


class PlanShareIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "plan_share_intent_conflict",
            admin_error_message("plan_share_intent_conflict"),
        )


class FeedbackIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "feedback_intent_conflict",
            admin_error_message("feedback_intent_conflict"),
        )


def _has_cjk(text: str) -> bool:
    """True when the text already carries user-facing Chinese copy."""
    return any("\u4e00" <= char <= "\u9fff" for char in text)
