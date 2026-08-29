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
