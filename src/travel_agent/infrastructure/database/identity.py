"""Minimal anonymous identity persistence for the first HTTP slice."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import String, text
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from travel_agent.application.common.clock import Clock
from travel_agent.application.planning.ports import IdGenerator

from .planning import Base


class AnonymousCredentialRow(Base):
    __tablename__ = "anonymous_credentials"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    device_installation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    expires_at: Mapped[str] = mapped_column(String(40), index=True)
    created_at: Mapped[str] = mapped_column(String(40))


class TokenGenerator(Protocol):
    def new_token(self) -> str: ...


class SecureTokenGenerator:
    def new_token(self) -> str:
        return secrets.token_urlsafe(32)


@dataclass(frozen=True, slots=True)
class AnonymousSession:
    principal_id: str
    access_token: str
    expires_at: datetime


class AnonymousIdentityService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        clock: Clock,
        ids: IdGenerator,
        tokens: TokenGenerator | None = None,
        lifetime: timedelta = timedelta(days=30),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock
        self._ids = ids
        self._tokens = tokens or SecureTokenGenerator()
        self._lifetime = lifetime

    def create(self, device_installation_id: str | None) -> AnonymousSession:
        now = self._clock.now()
        expires_at = now + self._lifetime
        token = self._tokens.new_token()
        principal_id = self._ids.new_id("principal")
        with self._session_factory() as session:
            session.add(
                AnonymousCredentialRow(
                    token_hash=_token_hash(token),
                    principal_id=principal_id,
                    device_installation_id=device_installation_id,
                    expires_at=expires_at.isoformat(),
                    created_at=now.isoformat(),
                )
            )
            session.commit()
        return AnonymousSession(principal_id, token, expires_at)

    def authenticate(self, token: str) -> str | None:
        now = self._clock.now()
        with self._session_factory() as session:
            row = session.get(AnonymousCredentialRow, _token_hash(token))
            if row is None or datetime.fromisoformat(row.expires_at) <= now:
                return None
            return row.principal_id

    def ready(self) -> bool:
        try:
            with self._session_factory() as session:
                session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
