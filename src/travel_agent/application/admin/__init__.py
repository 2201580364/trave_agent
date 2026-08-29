"""Administrator identity and RBAC use cases."""

from .errors import (
    AdminActorVersionConflictError,
    AdminAuthenticationError,
    AdminLoginNameConflictError,
    AdminOperationIntentConflictError,
    AdminPermissionDeniedError,
    AdminRoleSafetyError,
)
from .service import AdminIdentityService, AdminSession

__all__ = [
    "AdminActorVersionConflictError",
    "AdminAuthenticationError",
    "AdminIdentityService",
    "AdminLoginNameConflictError",
    "AdminOperationIntentConflictError",
    "AdminPermissionDeniedError",
    "AdminRoleSafetyError",
    "AdminSession",
]
