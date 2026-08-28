"""Deterministic public share tokens backed by an environment secret."""

from __future__ import annotations

import base64
import hashlib
import hmac


class HmacPlanShareTokenCodec:
    def __init__(self, secret: str) -> None:
        encoded = secret.encode("utf-8")
        if len(encoded) < 32:
            raise ValueError("plan share token secret must contain at least 32 bytes")
        self._secret = encoded

    def issue(self, plan_share_id: str) -> str:
        signature = hmac.new(
            self._secret,
            plan_share_id.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        encoded = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
        return f"ps1.{plan_share_id}.{encoded}"

    def hash(self, public_token: str) -> str:
        return hashlib.sha256(public_token.encode("utf-8")).hexdigest()
