"""Administrator identity, authorization, and audit domain primitives."""

from .models import (
    ADMIN_ROLE_KEYS,
    OM1_BOOTSTRAP_ROLES,
    AdminActor,
    AdminAuditEvent,
    AdminPrincipal,
    AdminRole,
    AdminSessionRecord,
    permissions_for_roles,
)

__all__ = [
    "ADMIN_ROLE_KEYS",
    "OM1_BOOTSTRAP_ROLES",
    "AdminActor",
    "AdminAuditEvent",
    "AdminPrincipal",
    "AdminRole",
    "AdminSessionRecord",
    "permissions_for_roles",
]
