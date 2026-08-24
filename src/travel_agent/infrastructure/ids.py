"""Opaque production ID generation."""

from __future__ import annotations

from uuid import uuid4


class UuidIdGenerator:
    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex}"
