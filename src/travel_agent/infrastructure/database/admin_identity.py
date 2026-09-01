"""SQLAlchemy persistence for administrator identity, RBAC, and audit."""

from __future__ import annotations

from datetime import datetime
from types import TracebackType
from typing import Self

from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    delete,
    func,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from travel_agent.application.admin.errors import (
    AdminActorVersionConflictError,
    AdminLoginNameConflictError,
    AdminOperationIntentConflictError,
)
from travel_agent.application.admin.service import ROLE_CATALOG
from travel_agent.domain.admin import (
    AdminActor,
    AdminAuditEvent,
    AdminRole,
    AdminSessionRecord,
)

from .planning import Base
from .place_catalog import SqlAlchemyPlaceCatalogRepository
from .place_review import SqlAlchemyPlaceReviewRepository


class AdminActorRow(Base):
    __tablename__ = "admin_actors"

    admin_actor_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    login_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    credential_digest: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), index=True)
    version: Mapped[int] = mapped_column(Integer)
    session_version: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))


class AdminRoleRow(Base):
    __tablename__ = "admin_roles"

    role_key: Mapped[str] = mapped_column(String(40), primary_key=True)
    description: Mapped[str] = mapped_column(String(200))
    enabled_milestone: Mapped[str] = mapped_column(String(16))


class AdminActorRoleRow(Base):
    __tablename__ = "admin_actor_roles"
    __table_args__ = (
        UniqueConstraint(
            "admin_actor_id", "role_key", name="uq_admin_actor_roles_actor_role"
        ),
        {
            "mysql_engine": "InnoDB",
            "mysql_charset": "utf8mb4",
            "mysql_collate": "utf8mb4_0900_ai_ci",
        },
    )

    admin_actor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("admin_actors.admin_actor_id"), primary_key=True
    )
    role_key: Mapped[str] = mapped_column(
        String(40), ForeignKey("admin_roles.role_key"), primary_key=True
    )
    granted_by: Mapped[str] = mapped_column(String(64))
    granted_at: Mapped[str] = mapped_column(String(40))


class AdminSessionRow(Base):
    __tablename__ = "admin_sessions"

    admin_session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    admin_actor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("admin_actors.admin_actor_id"), index=True
    )
    issued_role_keys: Mapped[list[str]] = mapped_column(JSON)
    session_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[str] = mapped_column(String(40), index=True)
    revoked_at: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    client_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(40))


class AdminAuditEventRow(Base):
    __tablename__ = "admin_audit_events"

    audit_event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("admin_actors.admin_actor_id"), index=True
    )
    actor_role: Mapped[str] = mapped_column(String(40), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(128), index=True)
    target_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), index=True)
    reason_text: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_id: Mapped[str] = mapped_column(String(100), index=True)
    operation_intent_id: Mapped[str | None] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    operation_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[str] = mapped_column(String(20), index=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    occurred_at: Mapped[str] = mapped_column(String(40), index=True)


class SqlAlchemyAdminActorRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def count(self) -> int:
        return int(self._session.scalar(select(func.count(AdminActorRow.admin_actor_id))) or 0)

    def get(self, actor_id: str) -> AdminActor | None:
        row = self._session.get(AdminActorRow, actor_id)
        return self._from_row(row) if row is not None else None

    def get_by_login(self, login_name: str) -> AdminActor | None:
        row = self._session.scalar(
            select(AdminActorRow).where(AdminActorRow.login_name == login_name)
        )
        return self._from_row(row) if row is not None else None

    def login_names_by_ids(self, actor_ids: tuple[str, ...]) -> dict[str, str]:
        unique_ids = tuple(dict.fromkeys(actor_ids))
        if not unique_ids:
            return {}
        rows = self._session.execute(
            select(AdminActorRow.admin_actor_id, AdminActorRow.login_name).where(
                AdminActorRow.admin_actor_id.in_(unique_ids)
            )
        )
        return {actor_id: login_name for actor_id, login_name in rows}

    def list(
        self,
        *,
        keyword: str | None,
        status: str | None,
        role_key: str | None,
        limit: int,
        offset: int,
    ) -> tuple[AdminActor, ...]:
        statement = select(AdminActorRow)
        if role_key is not None:
            statement = statement.join(
                AdminActorRoleRow,
                AdminActorRoleRow.admin_actor_id == AdminActorRow.admin_actor_id,
            ).where(AdminActorRoleRow.role_key == role_key)
        if status is not None:
            statement = statement.where(AdminActorRow.status == status)
        if keyword is not None:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    AdminActorRow.login_name.ilike(pattern),
                    AdminActorRow.admin_actor_id.ilike(pattern),
                )
            )
        rows = self._session.scalars(
            statement
            .distinct()
            .order_by(AdminActorRow.created_at.asc(), AdminActorRow.admin_actor_id.asc())
            .limit(limit)
            .offset(offset)
        )
        return tuple(self._from_row(row) for row in rows)

    def count_filtered(
        self, *, keyword: str | None, status: str | None, role_key: str | None
    ) -> int:
        statement = select(func.count(func.distinct(AdminActorRow.admin_actor_id)))
        if role_key is not None:
            statement = statement.join(
                AdminActorRoleRow,
                AdminActorRoleRow.admin_actor_id == AdminActorRow.admin_actor_id,
            ).where(AdminActorRoleRow.role_key == role_key)
        if status is not None:
            statement = statement.where(AdminActorRow.status == status)
        if keyword is not None:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    AdminActorRow.login_name.ilike(pattern),
                    AdminActorRow.admin_actor_id.ilike(pattern),
                )
            )
        return int(self._session.scalar(statement) or 0)

    def add(self, actor: AdminActor) -> None:
        self._session.add(
            AdminActorRow(
                admin_actor_id=actor.admin_actor_id,
                login_name=actor.login_name,
                credential_digest=actor.credential_digest,
                status=actor.status,
                version=actor.version,
                session_version=actor.session_version,
                created_at=actor.created_at.isoformat(),
                updated_at=actor.updated_at.isoformat(),
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise AdminLoginNameConflictError from exc
        for role_key in actor.role_keys:
            self._session.add(
                AdminActorRoleRow(
                    admin_actor_id=actor.admin_actor_id,
                    role_key=role_key,
                    granted_by=actor.admin_actor_id,
                    granted_at=actor.created_at.isoformat(),
                )
            )
        self._session.flush()

    def replace_roles(
        self,
        actor: AdminActor,
        *,
        expected_version: int,
        granted_by: str,
    ) -> None:
        statement = (
            update(AdminActorRow)
            .where(
                AdminActorRow.admin_actor_id == actor.admin_actor_id,
                AdminActorRow.version == expected_version,
            )
            .values(
                status=actor.status,
                version=actor.version,
                session_version=actor.session_version,
                updated_at=actor.updated_at.isoformat(),
            )
        )
        if self._session.execute(statement).rowcount != 1:
            current = self._session.scalar(
                select(AdminActorRow.version).where(
                    AdminActorRow.admin_actor_id == actor.admin_actor_id
                )
            )
            raise AdminActorVersionConflictError(expected_version, int(current or 0))
        self._session.execute(
            delete(AdminActorRoleRow).where(
                AdminActorRoleRow.admin_actor_id == actor.admin_actor_id
            )
        )
        for role_key in actor.role_keys:
            self._session.add(
                AdminActorRoleRow(
                    admin_actor_id=actor.admin_actor_id,
                    role_key=role_key,
                    granted_by=granted_by,
                    granted_at=actor.updated_at.isoformat(),
                )
            )
        self._session.flush()

    def count_active_with_role(self, role_key: str, *, lock: bool) -> int:
        statement = (
            select(AdminActorRow.admin_actor_id)
            .join(
                AdminActorRoleRow,
                AdminActorRoleRow.admin_actor_id == AdminActorRow.admin_actor_id,
            )
            .where(
                AdminActorRow.status == "active",
                AdminActorRoleRow.role_key == role_key,
            )
        )
        if lock:
            statement = statement.with_for_update()
        return len(tuple(self._session.scalars(statement)))

    def _from_row(self, row: AdminActorRow) -> AdminActor:
        role_keys = tuple(
            self._session.scalars(
                select(AdminActorRoleRow.role_key)
                .where(AdminActorRoleRow.admin_actor_id == row.admin_actor_id)
                .order_by(AdminActorRoleRow.role_key.asc())
            )
        )
        return AdminActor(
            row.admin_actor_id,
            row.login_name,
            row.credential_digest,
            row.status,
            row.version,
            row.session_version,
            role_keys,
            datetime.fromisoformat(row.created_at),
            datetime.fromisoformat(row.updated_at),
        )


class SqlAlchemyAdminRoleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_catalog(self, roles: tuple[AdminRole, ...]) -> None:
        for role in roles:
            row = self._session.get(AdminRoleRow, role.role_key)
            if row is None:
                self._session.add(
                    AdminRoleRow(
                        role_key=role.role_key,
                        description=role.description,
                        enabled_milestone=role.enabled_milestone,
                    )
                )
        self._session.flush()


class SqlAlchemyAdminSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_token_hash(self, token_hash: str) -> AdminSessionRecord | None:
        row = self._session.scalar(
            select(AdminSessionRow).where(AdminSessionRow.token_hash == token_hash)
        )
        return _session_from_row(row) if row is not None else None

    def add(self, session: AdminSessionRecord) -> None:
        self._session.add(
            AdminSessionRow(
                admin_session_id=session.admin_session_id,
                token_hash=session.token_hash,
                admin_actor_id=session.admin_actor_id,
                issued_role_keys=list(session.issued_role_keys),
                session_version=session.session_version,
                expires_at=session.expires_at.isoformat(),
                revoked_at=(
                    session.revoked_at.isoformat()
                    if session.revoked_at is not None
                    else None
                ),
                client_ip_hash=session.client_ip_hash,
                user_agent_hash=session.user_agent_hash,
                created_at=session.created_at.isoformat(),
            )
        )
        self._session.flush()

    def revoke(self, session_id: str, revoked_at: datetime) -> bool:
        statement = (
            update(AdminSessionRow)
            .where(
                AdminSessionRow.admin_session_id == session_id,
                AdminSessionRow.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at.isoformat())
        )
        result = self._session.execute(statement)
        return bool(result.rowcount == 1)


class SqlAlchemyAdminAuditRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, event: AdminAuditEvent) -> None:
        self._session.add(
            AdminAuditEventRow(
                audit_event_id=event.audit_event_id,
                actor_id=event.actor_id,
                actor_role=event.actor_role,
                action=event.action,
                target_type=event.target_type,
                target_id=event.target_id,
                target_revision=event.target_revision,
                before_digest=event.before_digest,
                after_digest=event.after_digest,
                reason_code=event.reason_code,
                reason_text=event.reason_text,
                request_id=event.request_id,
                operation_intent_id=event.operation_intent_id,
                operation_digest=event.operation_digest,
                result=event.result,
                error_code=event.error_code,
                occurred_at=event.occurred_at.isoformat(),
            )
        )
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise AdminOperationIntentConflictError from exc

    def get_by_operation_intent(
        self, operation_intent_id: str
    ) -> AdminAuditEvent | None:
        row = self._session.scalar(
            select(AdminAuditEventRow).where(
                AdminAuditEventRow.operation_intent_id == operation_intent_id
            )
        )
        return _audit_from_row(row) if row is not None else None

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
    ) -> tuple[AdminAuditEvent, ...]:
        statement = self._filtered_statement(
            actor_id=actor_id,
            actor_login_name=actor_login_name,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            keyword=keyword,
        )
        rows = self._session.scalars(
            statement.order_by(
                AdminAuditEventRow.occurred_at.desc(),
                AdminAuditEventRow.audit_event_id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        return tuple(_audit_from_row(row) for row in rows)

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
    ) -> int:
        statement = self._filtered_statement(
            actor_id=actor_id,
            actor_login_name=actor_login_name,
            target_type=target_type,
            target_id=target_id,
            action=action,
            result=result,
            keyword=keyword,
            count=True,
        )
        return int(self._session.scalar(statement) or 0)

    @staticmethod
    def _filtered_statement(
        *,
        actor_id: str | None,
        actor_login_name: str | None,
        target_type: str | None,
        target_id: str | None,
        action: str | None,
        result: str | None,
        keyword: str | None,
        count: bool = False,
    ):
        statement = (
            select(func.count()).select_from(AdminAuditEventRow)
            if count
            else select(AdminAuditEventRow)
        )
        if actor_login_name is not None or keyword is not None:
            statement = statement.join(
                AdminActorRow,
                AdminActorRow.admin_actor_id == AdminAuditEventRow.actor_id,
            )
        filters = (
            (AdminAuditEventRow.actor_id, actor_id),
            (AdminAuditEventRow.target_type, target_type),
            (AdminAuditEventRow.target_id, target_id),
            (AdminAuditEventRow.action, action),
            (AdminAuditEventRow.result, result),
        )
        for column, value in filters:
            if value is not None:
                statement = statement.where(column == value)
        if actor_login_name is not None:
            statement = statement.where(
                AdminActorRow.login_name.ilike(f"%{actor_login_name}%")
            )
        if keyword is not None:
            pattern = f"%{keyword}%"
            statement = statement.where(
                or_(
                    AdminAuditEventRow.actor_id.ilike(pattern),
                    AdminAuditEventRow.actor_role.ilike(pattern),
                    AdminAuditEventRow.action.ilike(pattern),
                    AdminAuditEventRow.target_type.ilike(pattern),
                    AdminAuditEventRow.target_id.ilike(pattern),
                    AdminAuditEventRow.reason_code.ilike(pattern),
                    AdminAuditEventRow.reason_text.ilike(pattern),
                    AdminAuditEventRow.request_id.ilike(pattern),
                    AdminAuditEventRow.error_code.ilike(pattern),
                    AdminActorRow.login_name.ilike(pattern),
                )
            )
        return statement


class SqlAlchemyAdminUnitOfWork:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.actors = SqlAlchemyAdminActorRepository(self._session)
        self.roles = SqlAlchemyAdminRoleRepository(self._session)
        self.sessions = SqlAlchemyAdminSessionRepository(self._session)
        self.audits = SqlAlchemyAdminAuditRepository(self._session)
        self.reviews = SqlAlchemyPlaceReviewRepository(self._session)
        self.catalog = SqlAlchemyPlaceCatalogRepository(self._session)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._session is not None:
            if exc_type is not None:
                self._session.rollback()
            self._session.close()
            self._session = None
        return None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("admin unit of work is not active")
        self._session.commit()


def _session_from_row(row: AdminSessionRow) -> AdminSessionRecord:
    return AdminSessionRecord(
        row.admin_session_id,
        row.token_hash,
        row.admin_actor_id,
        tuple(sorted(row.issued_role_keys)),
        row.session_version,
        datetime.fromisoformat(row.expires_at),
        datetime.fromisoformat(row.revoked_at) if row.revoked_at is not None else None,
        row.client_ip_hash,
        row.user_agent_hash,
        datetime.fromisoformat(row.created_at),
    )


def _audit_from_row(row: AdminAuditEventRow) -> AdminAuditEvent:
    return AdminAuditEvent(
        row.audit_event_id,
        row.actor_id,
        row.actor_role,
        row.action,
        row.target_type,
        row.target_id,
        row.target_revision,
        row.before_digest,
        row.after_digest,
        row.reason_code,
        row.reason_text,
        row.request_id,
        row.operation_intent_id,
        row.operation_digest,
        row.result,
        row.error_code,
        datetime.fromisoformat(row.occurred_at),
    )


def seed_admin_role_catalog(session: Session) -> None:
    """Seed roles for non-bootstrap schema creation tools and tests."""

    SqlAlchemyAdminRoleRepository(session).ensure_catalog(ROLE_CATALOG)
