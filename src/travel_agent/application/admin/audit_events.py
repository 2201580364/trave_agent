"""Shared audit-event construction for all admin write use cases (AUD-2).

Single authoritative helpers per ``.claude/rules/audit-logging.md``:

- ``build_audit_event`` — the ONLY way to construct ``AdminAuditEvent``
  (keyword-only; the dataclass's 17 positional fields must never be passed
  positionally);
- ``canonical_digest`` — the ONLY canonical-JSON SHA-256 digest used for
  ``before/after/operation`` digests (replaces the three private copies in
  service.py / review.py / holiday_calendar_sync.py);
- ``validate_audit_reason`` — the ONLY reason_code/reason_text validation
  (stable uppercase code + sensitive-word guard + length/control chars);
- ``representative_role`` — actor_role resolution with two intentional
  orderings (review flow prefers data_reviewer; identity flow prefers
  admin_security). The difference is semantic, not accidental: see
  audit-logging.md §6.

Behaviour is unchanged versus the three replaced private implementations.
"""

from __future__ import annotations

import hashlib
import json
import re

from travel_agent.domain.admin.models import AdminActor, AdminAuditEvent

REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
SENSITIVE_REASON_PATTERN = re.compile(
    r"(?i)(api[ _-]?key|access[ _-]?token|password|passwd|cookie|secret|私钥|密码|令牌)"
)

# audit-logging.md §6: two intentional role priority orderings.
_REVIEW_FLOW_ROLES = ("data_reviewer", "admin_security", "data_editor", "data_publisher")
_IDENTITY_FLOW_ROLES = (
    "admin_security",
    "data_publisher",
    "data_reviewer",
    "data_editor",
    "research_viewer",
    "content_moderator",
)


def canonical_digest(value: object) -> str:
    """Canonical-JSON SHA-256: the single digest algorithm for audit fields."""
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_audit_reason(
    reason_code: str, reason_text: str | None
) -> str | None:
    """Validate the audit reason pair; return the normalized reason_text."""
    if REASON_CODE_PATTERN.fullmatch(reason_code) is None:
        raise ValueError("reason_code must be a stable uppercase code")
    if reason_text and SENSITIVE_REASON_PATTERN.search(reason_text):
        raise ValueError("reason_text must not contain credentials")
    normalized = reason_text.strip() if reason_text else None
    if normalized and any(ord(char) < 32 for char in normalized):
        raise ValueError("reason_text must be printable")
    if normalized and len(normalized) > 500:
        raise ValueError("reason_text is too long")
    return normalized


def review_flow_role(role_keys: tuple[str, ...]) -> str:
    """actor_role for review/data flows (prefers data_reviewer)."""
    for role in _REVIEW_FLOW_ROLES:
        if role in role_keys:
            return role
    return "authenticated_admin"


def identity_flow_role(role_keys: tuple[str, ...]) -> str:
    """actor_role for identity/security flows (prefers admin_security)."""
    for role_key in _IDENTITY_FLOW_ROLES:
        if role_key in role_keys:
            return role_key
    return "authenticated_admin"


def build_audit_event(
    *,
    event_id: str,
    actor: AdminActor | None,
    actor_id_override: str | None = None,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str,
    target_revision: str | None = None,
    before_digest: str | None = None,
    after_digest: str | None = None,
    reason_code: str,
    reason_text: str | None = None,
    request_id: str,
    operation_intent_id: str | None = None,
    operation_digest: str | None = None,
    result: str,
    error_code: str | None = None,
    occurred_at: object,
) -> AdminAuditEvent:
    """Keyword-only construction of ``AdminAuditEvent`` (audit-logging.md §1.2).

    ``actor`` carries the acting AdminActor; ``actor_id_override`` covers the
    unauthenticated login-rejection case where the domain model is present but
    the action is attributed without an authenticated actor context. Exactly
    one of the two must be provided.
    """
    if (actor is None) == (actor_id_override is None):
        raise ValueError("provide exactly one of actor / actor_id_override")
    actor_id = actor_id_override if actor is None else actor.admin_actor_id
    return AdminAuditEvent(
        event_id,
        actor_id,
        actor_role,
        action,
        target_type,
        target_id,
        target_revision,
        before_digest,
        after_digest,
        reason_code,
        reason_text,
        request_id,
        operation_intent_id,
        operation_digest,
        result,
        error_code,
        occurred_at,  # type: ignore[arg-type]  # datetime; kept loose to avoid importing clock types
    )
