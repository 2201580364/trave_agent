"""Stable application errors independent of HTTP and persistence frameworks."""

from __future__ import annotations

from dataclasses import dataclass, field


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
            "草稿已在其他页面更新，请恢复最新版本后继续。",
            {
                "expected_version": expected_version,
                "current_version": current_version,
            },
        )


class GenerationIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "generation_intent_conflict",
            "该生成标识已经用于其他草稿版本。",
        )


class DraftNotReadyError(ApplicationError):
    def __init__(self, issues: tuple[str, ...]) -> None:
        super().__init__(
            "draft_not_ready",
            "草稿还有未完成的生成条件。",
            {"issues": issues},
        )


class InvalidStateTransitionError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_state_transition", message)


class TripRevisionConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "trip_revision_conflict",
            "行程已生成更新版本，请先恢复最新版本后再调整。",
        )


class InvalidAttractionReplacementError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__("invalid_attraction_replacement", message)


class PlanShareIntentConflictError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            "plan_share_intent_conflict",
            "该分享标识已经用于其他行程版本或模板。",
        )
