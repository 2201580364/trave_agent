"""Administrator authentication, server-side RBAC, and audit use cases."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Protocol, Self

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.errors import ApplicationError, ResourceNotFoundError
from travel_agent.application.planning.ports import IdGenerator
from travel_agent.domain.admin import (
    ADMIN_ROLE_KEYS,
    OM1_BOOTSTRAP_ROLES,
    AdminActor,
    AdminAuditEvent,
    AdminPrincipal,
    AdminRole,
    AdminSessionRecord,
    permissions_for_roles,
)

from .errors import (
    AdminActorVersionConflictError,
    AdminAuthenticationError,
    AdminLoginNameConflictError,
    AdminOperationIntentConflictError,
    AdminPermissionDeniedError,
    AdminRoleSafetyError,
)

_LOGIN_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,63}$")
_REASON_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
_SENSITIVE_REASON_PATTERN = re.compile(
    r"(?i)(api[ _-]?key|access[ _-]?token|password|passwd|cookie|secret|私钥|密码|令牌)"
)
_DUMMY_ADMIN_CREDENTIAL = (
    "scrypt$16384$8$1$"
    + ("00" * 16)
    + "$"
    + ("00" * 32)
)

ROLE_CATALOG = (
    AdminRole("data_editor", "编辑候选地点和 Revision", "OM1"),
    AdminRole("data_reviewer", "审核地点事实和关系裁决", "OM1"),
    AdminRole("data_publisher", "运行发布门并发布研究快照", "OM1"),
    AdminRole("research_viewer", "只读查看研究数据和快照", "OM1"),
    AdminRole("content_moderator", "处理评论和社区内容", "OM3"),
    AdminRole("admin_security", "管理管理员身份、角色和安全审计", "OM1"),
)


class AdminActorRepository(Protocol):
    def count(self) -> int: ...

    def get(self, actor_id: str) -> AdminActor | None: ...

    def get_by_login(self, login_name: str) -> AdminActor | None: ...

    def login_names_by_ids(self, actor_ids: tuple[str, ...]) -> dict[str, str]: ...

    def list(
        self,
        *,
        keyword: str | None,
        status: str | None,
        role_key: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminActor, ...]: ...

    def count_filtered(
        self, *, keyword: str | None, status: str | None, role_key: str | None
    ) -> int: ...

    def add(self, actor: AdminActor) -> None: ...

    def replace_roles(
        self,
        actor: AdminActor,
        *,
        expected_version: int,
        granted_by: str,
    ) -> None: ...

    def count_active_with_role(self, role_key: str, *, lock: bool) -> int: ...


class AdminRoleRepository(Protocol):
    def ensure_catalog(self, roles: tuple[AdminRole, ...]) -> None: ...


class AdminSessionRepository(Protocol):
    def get_by_token_hash(self, token_hash: str) -> AdminSessionRecord | None: ...

    def add(self, session: AdminSessionRecord) -> None: ...

    def revoke(self, session_id: str, revoked_at: datetime) -> bool: ...


class AdminAuditRepository(Protocol):
    def add(self, event: AdminAuditEvent) -> None: ...

    def get_by_operation_intent(
        self, operation_intent_id: str
    ) -> AdminAuditEvent | None: ...

    def list(
        self,
        *,
        actor_id: str | None,
        actor_login_name: str | None,
        target_type: str | None,
        target_id: str | None,
        action: str | None,
        result: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminAuditEvent, ...]: ...

    def count(
        self,
        *,
        actor_id: str | None,
        actor_login_name: str | None,
        target_type: str | None,
        target_id: str | None,
        action: str | None,
        result: str | None,
        keyword: str | None,
    ) -> int: ...


class AdminUnitOfWork(Protocol):
    actors: AdminActorRepository
    roles: AdminRoleRepository
    sessions: AdminSessionRepository
    audits: AdminAuditRepository

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...

    def commit(self) -> None: ...


class AdminTokenGenerator(Protocol):
    def new_token(self) -> str: ...


class SecureAdminTokenGenerator:
    def new_token(self) -> str:
        return secrets.token_urlsafe(48)


@dataclass(frozen=True, slots=True)
class AdminSession:
    principal: AdminPrincipal
    access_token: str


class AdminIdentityService:
    def __init__(
        self,
        uow_factory: Callable[[], AdminUnitOfWork],
        clock: Clock,
        ids: IdGenerator,
        tokens: AdminTokenGenerator | None = None,
        lifetime: timedelta = timedelta(hours=8),
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock
        self._ids = ids
        self._tokens = tokens or SecureAdminTokenGenerator()
        self._lifetime = lifetime

    def bootstrap_initial_admin(self, login_name: str, password: str) -> bool:
        login_name = _validate_login_name(login_name)
        _validate_password(password)
        now = _utc(self._clock.now())
        with self._uow_factory() as uow:
            uow.roles.ensure_catalog(ROLE_CATALOG)
            if uow.actors.count() != 0:
                return False
            actor = AdminActor(
                self._ids.new_id("admin_actor"),
                login_name,
                hash_admin_password(password),
                "active",
                1,
                1,
                tuple(sorted(OM1_BOOTSTRAP_ROLES)),
                now,
                now,
            )
            uow.actors.add(actor)
            uow.audits.add(
                self._event(
                    actor,
                    actor_role="admin_security",
                    action="ADMIN_ACTOR_BOOTSTRAPPED",
                    target_type="admin_actor",
                    target_id=actor.admin_actor_id,
                    before_digest=None,
                    after_digest=_actor_digest(actor),
                    reason_code="INITIAL_ADMIN_BOOTSTRAP",
                    reason_text=None,
                    request_id="startup-bootstrap",
                    result="succeeded",
                )
            )
            uow.commit()
            return True

    def create_session(
        self,
        login_name: str,
        password: str,
        *,
        request_id: str,
        client_ip: str | None,
        user_agent: str | None,
    ) -> AdminSession:
        now = _utc(self._clock.now())
        normalized_login = login_name.strip()
        with self._uow_factory() as uow:
            uow.roles.ensure_catalog(ROLE_CATALOG)
            actor = uow.actors.get_by_login(normalized_login)
            password_matches = verify_admin_password(
                password,
                actor.credential_digest if actor is not None else _DUMMY_ADMIN_CREDENTIAL,
            )
            valid = (
                actor is not None
                and actor.status == "active"
                and password_matches
            )
            if not valid:
                if actor is not None:
                    uow.audits.add(
                        self._event(
                            actor,
                            actor_role="unauthenticated",
                            action="ADMIN_SESSION_CREATE",
                            target_type="admin_actor",
                            target_id=actor.admin_actor_id,
                            before_digest=None,
                            after_digest=None,
                            reason_code="ADMIN_LOGIN_REJECTED",
                            reason_text=None,
                            request_id=request_id,
                            result="rejected",
                            error_code="admin_authentication_required",
                        )
                    )
                    uow.commit()
                raise AdminAuthenticationError
            assert actor is not None
            token = self._tokens.new_token()
            expires_at = now + self._lifetime
            record = AdminSessionRecord(
                self._ids.new_id("admin_session"),
                _token_hash(token),
                actor.admin_actor_id,
                actor.role_keys,
                actor.session_version,
                expires_at,
                None,
                _optional_digest(client_ip),
                _optional_digest(user_agent),
                now,
            )
            uow.sessions.add(record)
            uow.audits.add(
                self._event(
                    actor,
                    actor_role=_representative_role(actor.role_keys),
                    action="ADMIN_SESSION_CREATE",
                    target_type="admin_session",
                    target_id=record.admin_session_id,
                    before_digest=None,
                    after_digest=_session_digest(record),
                    reason_code="ADMIN_LOGIN_SUCCEEDED",
                    reason_text=None,
                    request_id=request_id,
                    result="succeeded",
                )
            )
            uow.commit()
        principal = _principal(actor, record)
        return AdminSession(principal, token)

    def authenticate(self, token: str) -> AdminPrincipal:
        now = _utc(self._clock.now())
        token_hash = _token_hash(token)
        with self._uow_factory() as uow:
            record = uow.sessions.get_by_token_hash(token_hash)
            if record is None or record.revoked_at is not None or record.expires_at <= now:
                raise AdminAuthenticationError
            actor = uow.actors.get(record.admin_actor_id)
            if (
                actor is None
                or actor.status != "active"
                or actor.session_version != record.session_version
                or actor.role_keys != record.issued_role_keys
            ):
                raise AdminAuthenticationError
            return _principal(actor, record)

    def revoke_current(self, principal: AdminPrincipal, *, request_id: str) -> None:
        now = _utc(self._clock.now())
        with self._uow_factory() as uow:
            actor = uow.actors.get(principal.admin_actor_id)
            record = uow.sessions.get_by_token_hash(principal.token_hash)
            if actor is None or record is None or record.revoked_at is not None:
                raise AdminAuthenticationError
            if not uow.sessions.revoke(record.admin_session_id, now):
                raise AdminAuthenticationError
            uow.audits.add(
                self._event(
                    actor,
                    actor_role=_representative_role(principal.role_keys),
                    action="ADMIN_SESSION_REVOKE",
                    target_type="admin_session",
                    target_id=record.admin_session_id,
                    before_digest=_session_digest(record),
                    after_digest=_session_digest(replace(record, revoked_at=now)),
                    reason_code="ADMIN_LOGOUT",
                    reason_text=None,
                    request_id=request_id,
                    result="succeeded",
                )
            )
            uow.commit()

    def list_actors(
        self,
        principal: AdminPrincipal,
        *,
        keyword: str | None,
        status: str | None,
        role_key: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminActor, ...]:
        self.require_permission(principal, "admin:actor:read")
        with self._uow_factory() as uow:
            return uow.actors.list(
                keyword=_optional_query(keyword),
                status=status,
                role_key=role_key,
                limit=limit,
                offset=offset,
            )

    def count_actors(
        self,
        principal: AdminPrincipal,
        *,
        keyword: str | None,
        status: str | None,
        role_key: str | None,
    ) -> int:
        self.require_permission(principal, "admin:actor:read")
        with self._uow_factory() as uow:
            return uow.actors.count_filtered(
                keyword=_optional_query(keyword), status=status, role_key=role_key
            )

    def create_actor(
        self,
        principal: AdminPrincipal,
        *,
        login_name: str,
        initial_password: str,
        role_keys: tuple[str, ...],
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> tuple[AdminActor, bool]:
        normalized_login = _validate_login_name(login_name)
        _validate_password(initial_password)
        normalized_roles = _validate_role_keys(role_keys)
        normalized_reason = _validate_reason(reason_code, reason_text)
        operation_digest = _canonical_digest(
            {
                "login_name": normalized_login,
                "role_keys": normalized_roles,
                "reason_code": reason_code,
                "reason_text": normalized_reason,
            }
        )
        with self._uow_factory() as uow:
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                actor = uow.actors.get(existing.target_id)
                if (
                    existing.operation_digest != operation_digest
                    or actor is None
                    or not verify_admin_password(
                        initial_password, actor.credential_digest
                    )
                ):
                    raise AdminOperationIntentConflictError
                return actor, True

            requester = uow.actors.get(principal.admin_actor_id)
            if requester is None:
                raise AdminAuthenticationError
            if not principal.has_permission("admin:actor:roles:write"):
                uow.audits.add(
                    self._event(
                        requester,
                        actor_role=_representative_role(principal.role_keys),
                        action="ADMIN_ACTOR_CREATE",
                        target_type="admin_actor_login",
                        target_id=normalized_login,
                        before_digest=None,
                        after_digest=None,
                        reason_code=reason_code,
                        reason_text=normalized_reason,
                        request_id=request_id,
                        operation_intent_id=operation_intent_id,
                        operation_digest=operation_digest,
                        result="rejected",
                        error_code="admin_permission_denied",
                    )
                )
                uow.commit()
                raise AdminPermissionDeniedError("admin:actor:roles:write")
            if uow.actors.get_by_login(normalized_login) is not None:
                raise AdminLoginNameConflictError

            now = _utc(self._clock.now())
            actor = AdminActor(
                self._ids.new_id("admin_actor"),
                normalized_login,
                hash_admin_password(initial_password),
                "active",
                1,
                1,
                normalized_roles,
                now,
                now,
            )
            uow.actors.add(actor)
            uow.audits.add(
                self._event(
                    requester,
                    actor_role="admin_security",
                    action="ADMIN_ACTOR_CREATE",
                    target_type="admin_actor",
                    target_id=actor.admin_actor_id,
                    target_revision="1",
                    before_digest=None,
                    after_digest=_actor_digest(actor),
                    reason_code=reason_code,
                    reason_text=normalized_reason,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    result="succeeded",
                )
            )
            uow.commit()
            return actor, False

    def change_roles(
        self,
        principal: AdminPrincipal,
        actor_id: str,
        *,
        expected_version: int,
        role_keys: tuple[str, ...],
        operation_intent_id: str,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
    ) -> tuple[AdminActor, bool]:
        normalized_roles = _validate_role_keys(role_keys)
        normalized_reason = _validate_reason(reason_code, reason_text)
        operation_digest = _canonical_digest(
            {
                "actor_id": actor_id,
                "expected_version": expected_version,
                "role_keys": normalized_roles,
                "reason_code": reason_code,
                "reason_text": normalized_reason,
            }
        )
        with self._uow_factory() as uow:
            existing = uow.audits.get_by_operation_intent(operation_intent_id)
            if existing is not None:
                if existing.operation_digest != operation_digest:
                    raise AdminOperationIntentConflictError
                actor = uow.actors.get(actor_id)
                if actor is None:
                    raise ResourceNotFoundError
                if existing.result == "succeeded":
                    return actor, True
                if existing.error_code == "admin_permission_denied":
                    raise AdminPermissionDeniedError("admin:actor:roles:write")
                if existing.error_code == "admin_actor_version_conflict":
                    raise AdminActorVersionConflictError(expected_version, actor.version)
                raise AdminRoleSafetyError("该角色变更已被安全门拒绝。")

            requester = uow.actors.get(principal.admin_actor_id)
            target = uow.actors.get(actor_id)
            if requester is None:
                raise AdminAuthenticationError
            if target is None:
                raise ResourceNotFoundError

            error: ApplicationError | None = None
            if not principal.has_permission("admin:actor:roles:write"):
                error = AdminPermissionDeniedError("admin:actor:roles:write")
            elif target.version != expected_version:
                error = AdminActorVersionConflictError(expected_version, target.version)
            elif (
                "admin_security" in target.role_keys
                and "admin_security" not in normalized_roles
                and uow.actors.count_active_with_role("admin_security", lock=True) <= 1
            ):
                error = AdminRoleSafetyError(
                    "不能移除最后一个有效 admin_security；请先建立恢复管理员。"
                )
            if error is not None:
                uow.audits.add(
                    self._event(
                        requester,
                        actor_role=_representative_role(principal.role_keys),
                        action="ADMIN_ACTOR_ROLES_CHANGE",
                        target_type="admin_actor",
                        target_id=actor_id,
                        target_revision=str(target.version),
                        before_digest=_actor_digest(target),
                        after_digest=None,
                        reason_code=reason_code,
                        reason_text=normalized_reason,
                        request_id=request_id,
                        operation_intent_id=operation_intent_id,
                        operation_digest=operation_digest,
                        result="rejected",
                        error_code=error.code,
                    )
                )
                uow.commit()
                raise error

            updated = replace(
                target,
                version=target.version + 1,
                session_version=target.session_version + 1,
                role_keys=normalized_roles,
                updated_at=_utc(self._clock.now()),
            )
            try:
                uow.actors.replace_roles(
                    updated,
                    expected_version=expected_version,
                    granted_by=requester.admin_actor_id,
                )
            except AdminActorVersionConflictError as conflict:
                uow.audits.add(
                    self._event(
                        requester,
                        actor_role="admin_security",
                        action="ADMIN_ACTOR_ROLES_CHANGE",
                        target_type="admin_actor",
                        target_id=actor_id,
                        target_revision=str(target.version),
                        before_digest=_actor_digest(target),
                        after_digest=None,
                        reason_code=reason_code,
                        reason_text=normalized_reason,
                        request_id=request_id,
                        operation_intent_id=operation_intent_id,
                        operation_digest=operation_digest,
                        result="rejected",
                        error_code=conflict.code,
                    )
                )
                uow.commit()
                raise
            uow.audits.add(
                self._event(
                    requester,
                    actor_role="admin_security",
                    action="ADMIN_ACTOR_ROLES_CHANGE",
                    target_type="admin_actor",
                    target_id=actor_id,
                    target_revision=str(updated.version),
                    before_digest=_actor_digest(target),
                    after_digest=_actor_digest(updated),
                    reason_code=reason_code,
                    reason_text=normalized_reason,
                    request_id=request_id,
                    operation_intent_id=operation_intent_id,
                    operation_digest=operation_digest,
                    result="succeeded",
                )
            )
            uow.commit()
            return updated, False

    def list_audit_events(
        self,
        principal: AdminPrincipal,
        *,
        actor_id: str | None,
        actor_login_name: str | None,
        target_type: str | None,
        target_id: str | None,
        action: str | None,
        result: str | None,
        keyword: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminAuditEvent, ...]:
        self.require_permission(principal, "admin:audit:read")
        with self._uow_factory() as uow:
            return uow.audits.list(
                actor_id=actor_id,
                actor_login_name=_optional_query(actor_login_name),
                target_type=target_type,
                target_id=target_id,
                action=action,
                result=result,
                keyword=_optional_query(keyword),
                limit=limit,
                offset=offset,
            )

    def count_audit_events(
        self,
        principal: AdminPrincipal,
        *,
        actor_id: str | None,
        actor_login_name: str | None,
        target_type: str | None,
        target_id: str | None,
        action: str | None,
        result: str | None,
        keyword: str | None,
    ) -> int:
        self.require_permission(principal, "admin:audit:read")
        with self._uow_factory() as uow:
            return uow.audits.count(
                actor_id=actor_id,
                actor_login_name=_optional_query(actor_login_name),
                target_type=target_type,
                target_id=target_id,
                action=action,
                result=result,
                keyword=_optional_query(keyword),
            )

    def audit_actor_login_names(
        self,
        principal: AdminPrincipal,
        *,
        actor_ids: tuple[str, ...],
    ) -> dict[str, str]:
        self.require_permission(principal, "admin:audit:read")
        if not actor_ids:
            return {}
        with self._uow_factory() as uow:
            return uow.actors.login_names_by_ids(actor_ids)

    @staticmethod
    def require_permission(principal: AdminPrincipal, permission: str) -> None:
        if not principal.has_permission(permission):
            raise AdminPermissionDeniedError(permission)

    def _event(
        self,
        actor: AdminActor,
        *,
        actor_role: str,
        action: str,
        target_type: str,
        target_id: str,
        before_digest: str | None,
        after_digest: str | None,
        reason_code: str,
        reason_text: str | None,
        request_id: str,
        result: str,
        target_revision: str | None = None,
        operation_intent_id: str | None = None,
        operation_digest: str | None = None,
        error_code: str | None = None,
    ) -> AdminAuditEvent:
        return AdminAuditEvent(
            self._ids.new_id("admin_audit"),
            actor.admin_actor_id,
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
            _utc(self._clock.now()),
        )


def hash_admin_password(password: str) -> str:
    _validate_password(password)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32
    )
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def verify_admin_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_hex, digest_hex = encoded.split("$")
        if algorithm != "scrypt":
            return False
        n_value, r_value, p_value = int(n), int(r), int(p)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        if (
            (n_value, r_value, p_value) != (2**14, 8, 1)
            or len(salt) != 16
            or len(expected) != 32
        ):
            return False
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n_value,
            r=r_value,
            p=p_value,
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _principal(actor: AdminActor, session: AdminSessionRecord) -> AdminPrincipal:
    return AdminPrincipal(
        actor.admin_actor_id,
        actor.login_name,
        actor.role_keys,
        permissions_for_roles(actor.role_keys),
        session.admin_session_id,
        session.token_hash,
        session.expires_at,
    )


def _validate_login_name(value: str) -> str:
    normalized = value.strip()
    if not _LOGIN_NAME_PATTERN.fullmatch(normalized):
        raise ValueError(
            "admin login name must be 3-64 ASCII letters, digits, dot, underscore, or dash"
        )
    return normalized


def _validate_password(password: str) -> None:
    if len(password) < 14 or len(password.encode("utf-8")) > 256:
        raise ValueError("admin password must be 14-256 bytes")
    if password.strip() != password:
        raise ValueError("admin password cannot start or end with whitespace")


def _validate_role_keys(role_keys: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(sorted(set(role_keys)))
    unknown = tuple(sorted(set(normalized).difference(ADMIN_ROLE_KEYS)))
    if unknown:
        raise ValueError(f"unknown admin roles: {', '.join(unknown)}")
    if not normalized:
        raise ValueError("an active admin actor must retain at least one role")
    return normalized


def _validate_reason(reason_code: str, reason_text: str | None) -> str | None:
    if not _REASON_CODE_PATTERN.fullmatch(reason_code):
        raise ValueError("reason_code must be a stable uppercase code")
    if reason_text is None:
        return None
    normalized = reason_text.strip()
    if not normalized:
        return None
    if len(normalized) > 500 or any(ord(char) < 32 for char in normalized):
        raise ValueError("reason_text must be printable and no longer than 500 characters")
    if _SENSITIVE_REASON_PATTERN.search(normalized):
        raise ValueError("reason_text must not contain secrets or credential material")
    return normalized


def _representative_role(role_keys: tuple[str, ...]) -> str:
    for role_key in (
        "admin_security",
        "data_publisher",
        "data_reviewer",
        "data_editor",
        "research_viewer",
        "content_moderator",
    ):
        if role_key in role_keys:
            return role_key
    return "authenticated_admin"


def _optional_query(value: str | None) -> str | None:
    normalized = value.strip() if value else ""
    return normalized or None


def _actor_digest(actor: AdminActor) -> str:
    return _canonical_digest(
        {
            "admin_actor_id": actor.admin_actor_id,
            "login_name": actor.login_name,
            "status": actor.status,
            "version": actor.version,
            "session_version": actor.session_version,
            "role_keys": actor.role_keys,
        }
    )


def _session_digest(session: AdminSessionRecord) -> str:
    return _canonical_digest(
        {
            "admin_session_id": session.admin_session_id,
            "admin_actor_id": session.admin_actor_id,
            "session_version": session.session_version,
            "issued_role_keys": session.issued_role_keys,
            "expires_at": session.expires_at.isoformat(),
            "revoked_at": (
                session.revoked_at.isoformat() if session.revoked_at is not None else None
            ),
        }
    )


def _canonical_digest(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _optional_digest(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("admin identity clock must return a timezone-aware datetime")
    return value.astimezone(UTC)
