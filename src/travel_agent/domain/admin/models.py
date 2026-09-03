"""Immutable administrator identity and audit values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

ADMIN_ROLE_KEYS = (
    "data_editor",
    "data_reviewer",
    "data_publisher",
    "research_viewer",
    "content_moderator",
    "admin_security",
)

OM1_BOOTSTRAP_ROLES = (
    "admin_security",
    "data_editor",
    "data_publisher",
    "data_reviewer",
    "research_viewer",
)

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "data_editor": frozenset(
        {
            "admin:session:self",
            "place:candidate:read",
            "place:candidate:write",
            "place:revision:write",
            "place:review:request",
            "holiday:calendar:read",
            "holiday:calendar:write",
        }
    ),
    "data_reviewer": frozenset(
        {
            "admin:session:self",
            "place:candidate:read",
            "place:review:read",
            "place:review:decide",
            "holiday:calendar:read",
        }
    ),
    "data_publisher": frozenset(
        {
            "admin:session:self",
            "place:candidate:read",
            "place:publication:check",
            "place:publication:write",
            "research:snapshot:read",
            "research:snapshot:write",
            "holiday:calendar:read",
        }
    ),
    "research_viewer": frozenset(
        {
            "admin:session:self",
            "place:candidate:read",
            "research:snapshot:read",
            "holiday:calendar:read",
        }
    ),
    "content_moderator": frozenset(
        {
            "admin:session:self",
            "community:moderation:read",
            "community:moderation:write",
        }
    ),
    "admin_security": frozenset(
        {
            "admin:session:self",
            "admin:actor:read",
            "admin:actor:roles:write",
            "admin:audit:read",
            "holiday:calendar:read",
            "holiday:calendar:write",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class AdminRole:
    role_key: str
    description: str
    enabled_milestone: str


@dataclass(frozen=True, slots=True)
class AdminActor:
    admin_actor_id: str
    login_name: str
    credential_digest: str
    status: str
    version: int
    session_version: int
    role_keys: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class AdminSessionRecord:
    admin_session_id: str
    token_hash: str
    admin_actor_id: str
    issued_role_keys: tuple[str, ...]
    session_version: int
    expires_at: datetime
    revoked_at: datetime | None
    client_ip_hash: str | None
    user_agent_hash: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AdminPrincipal:
    admin_actor_id: str
    login_name: str
    role_keys: tuple[str, ...]
    permissions: tuple[str, ...]
    admin_session_id: str
    token_hash: str
    expires_at: datetime

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions


@dataclass(frozen=True, slots=True)
class AdminAuditEvent:
    audit_event_id: str
    actor_id: str
    actor_role: str
    action: str
    target_type: str
    target_id: str
    target_revision: str | None
    before_digest: str | None
    after_digest: str | None
    reason_code: str
    reason_text: str | None
    request_id: str
    operation_intent_id: str | None
    operation_digest: str | None
    result: str
    error_code: str | None
    occurred_at: datetime


def permissions_for_roles(role_keys: tuple[str, ...]) -> tuple[str, ...]:
    permissions: set[str] = set()
    for role_key in role_keys:
        permissions.update(_ROLE_PERMISSIONS.get(role_key, ()))
    return tuple(sorted(permissions))
