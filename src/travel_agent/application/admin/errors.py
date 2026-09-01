"""Stable administrator identity and authorization errors."""

from travel_agent.application.common.errors import ApplicationError


class AdminAuthenticationError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_authentication_required",
            "管理员会话缺失、已失效或已撤销。",
        )


class AdminPermissionDeniedError(ApplicationError):
    def __init__(self, permission: str) -> None:
        super().__init__(
            "admin_permission_denied",
            "当前管理员角色无权执行该操作。",
            {"required_permission": permission},
        )


class AdminActorVersionConflictError(ApplicationError):
    def __init__(self, expected_version: int, current_version: int) -> None:
        super().__init__(
            "admin_actor_version_conflict",
            "管理员角色已被其他操作更新，请刷新后重试。",
            {
                "expected_version": expected_version,
                "current_version": current_version,
            },
        )


class AdminOperationIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_operation_intent_conflict",
            "该管理操作标识已经用于其他载荷。",
        )


class AdminLoginNameConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "admin_login_name_conflict",
            "该管理员登录名已存在。",
        )


class AdminRoleSafetyError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("admin_role_safety_violation", message)


class ReviewTaskNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("review_task_not_found", "review task was not found")


class ReviewTaskConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("review_task_conflict", "review task has changed; refresh and retry")


class ReviewRevisionNotApprovableError(ApplicationError):
    def __init__(self) -> None:
        super().__init__("review_revision_not_approvable", "candidate revision is not approvable")


class ReviewRevisionNotCandidateError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "review_revision_not_candidate",
            "only candidate revisions can enter human review",
        )


class PlaceRevisionVersionConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "place_revision_version_conflict",
            "Revision 已被其他操作更新，请刷新后重试。",
        )


class SourceRecordInUseError(ApplicationError):
    def __init__(self, references: tuple[str, ...]) -> None:
        super().__init__(
            "source_record_in_use",
            "当前来源仍被地点证据引用，请先把这些证据改用其他来源。",
            {"references": references},
        )


class SourceRecordValidationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("source_record_validation_failed", message)


class PublicationGateRejectedError(ApplicationError):
    """A revision/projection failed the stable publication gate."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        super().__init__(
            "publication_gate_rejected",
            "place revision cannot be published until all publication gates pass",
            {"reason_codes": normalized},
        )


class ProjectionPreparationRejectedError(ApplicationError):
    """A verified revision cannot yet produce a usable solver projection."""

    def __init__(self, reason_codes: tuple[str, ...]) -> None:
        normalized = tuple(sorted(set(reason_codes)))
        super().__init__(
            "projection_preparation_rejected",
            "Projection 准备未完成，请先补齐所需证据。",
            {"reason_codes": normalized},
        )
