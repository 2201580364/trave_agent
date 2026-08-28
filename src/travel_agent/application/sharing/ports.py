"""Ports required by the sharing application layer."""

from __future__ import annotations

from typing import Protocol


class PlanShareTokenCodec(Protocol):
    def issue(self, plan_share_id: str) -> str: ...

    def hash(self, public_token: str) -> str: ...
