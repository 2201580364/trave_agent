"""Stable administrator identity and authorization errors.

User copy lives in ``error_messages`` (single source of truth); this module
only wires stable machine codes to it and attaches whitelisted details.
"""

from travel_agent.application.common.error_messages import (
    admin_error_message,
    summarize_error_details,
)
from travel_agent.application.common.errors import ApplicationError


class AdminAuthenticationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_authentication_required",
            admin_error_message("admin_authentication_required"),
        )


class AdminPermissionDeniedError(ApplicationError):
    def __init__(self, permission: str) -> None:
        super().__init__(
            "admin_permission_denied",
            admin_error_message("admin_permission_denied"),
            {"required_permission": permission},
        )


class AdminActorVersionConflictError(ApplicationError):
    def __init__(self, expected_version: int, current_version: int) -> None:
        super().__init__(
            "admin_actor_version_conflict",
            admin_error_message("admin_actor_version_conflict"),
            {
                "expected_version": expected_version,
                "current_version": current_version,
            },
        )


class AdminOperationIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_operation_intent_conflict",
            admin_error_message("admin_operation_intent_conflict"),
        )


class AdminLoginNameConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_login_name_conflict",
            admin_error_message("admin_login_name_conflict"),
        )


class AdminRoleSafetyError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("admin_role_safety_violation", message)


class ReviewTaskNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "review_task_not_found",
            admin_error_message("review_task_not_found"),
        )


class ReviewTaskConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "review_task_conflict",
            admin_error_message("review_task_conflict"),
        )


class ReviewRevisionNotApprovableError(ApplicationError):
    def __init__(
        self,
        *,
        missing_checks: tuple[str, ...] = (),
        pending_review_checks: tuple[str, ...] = (),
        not_candidate: bool = False,
    ) -> None:
        details: dict[str, object] = {
            "missing_checks": list(missing_checks),
            "pending_review_checks": list(pending_review_checks),
            "not_candidate": not_candidate,
        }
        super().__init__(
            "review_revision_not_approvable",
            admin_error_message("review_revision_not_approvable")
            + summarize_error_details("review_revision_not_approvable", details),
            details,
        )


class ReviewRevisionNotCandidateError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "review_revision_not_candidate",
            admin_error_message("review_revision_not_candidate"),
        )


class PlaceRevisionVersionConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "place_revision_version_conflict",
            admin_error_message("place_revision_version_conflict"),
        )


class SourceRecordInUseError(ApplicationError):
    def __init__(self, references: tuple[str, ...]) -> None:
        details: dict[str, object] = {"references": references}
        super().__init__(
            "source_record_in_use",
            admin_error_message("source_record_in_use")
            + summarize_error_details("source_record_in_use", details),
            details,
        )


class SourceRecordValidationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("source_record_validation_failed", message)


class PublicationGateRejectedError(ApplicationError):
    """A revision/projection failed the stable publication gate."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        details: dict[str, object] = {"reason_codes": normalized}
        super().__init__(
            "publication_gate_rejected",
            admin_error_message("publication_gate_rejected")
            + summarize_error_details("publication_gate_rejected", details),
            details,
        )


class ProjectionPreparationRejectedError(ApplicationError):
    """A verified revision cannot yet produce a usable solver projection."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        details: dict[str, object] = {"reason_codes": normalized}
        super().__init__(
            "projection_preparation_rejected",
            admin_error_message("projection_preparation_rejected")
            + summarize_error_details("projection_preparation_rejected", details),
            details,
        )
