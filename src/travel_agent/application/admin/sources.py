"""Governed source channels available to place evidence editors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from travel_agent.data_governance import (
    canonical_json_sha256,
    load_json_object,
    validate_governance_bundle,
)


_PLACE_FIELD_PREFIXES = ("place.", "access.", "time.", "experience.", "relation.")
_SENSITIVE_QUERY_KEYS = frozenset(
    (
    "key",
    "token",
    "secret",
    "password",
    "passwd",
    "signature",
    "credential",
    "authorization",
    )
)


@dataclass(frozen=True, slots=True)
class GovernedSourceChannel:
    source_id: str
    display_name: str
    source_kind: str
    decision: str
    collection_modes: tuple[str, ...]
    base_urls: tuple[str, ...]
    conditions: tuple[str, ...]
    registry_id: str
    registry_sha256: str
    field_dictionary_id: str
    field_dictionary_sha256: str


class SourceRecordInputError(ValueError):
    """Raised when an editor input violates the approved source registry."""


class GovernedSourceCatalog:
    def __init__(self, registry: dict[str, object], field_dictionary: dict[str, object]) -> None:
        validate_governance_bundle(registry, field_dictionary)
        self._registry = registry
        self._field_dictionary = field_dictionary
        self._registry_sha256 = canonical_json_sha256(registry)
        self._field_dictionary_sha256 = canonical_json_sha256(field_dictionary)
        self._channels = self._build_channels()

    @classmethod
    def from_files(cls, registry_path: Path, field_dictionary_path: Path) -> GovernedSourceCatalog:
        return cls(load_json_object(registry_path), load_json_object(field_dictionary_path))

    def list_channels(self) -> tuple[GovernedSourceChannel, ...]:
        return tuple(sorted(self._channels.values(), key=lambda item: item.display_name))

    def require_valid_input(
        self, *, source_id: str, source_url: str, collection_mode: str
    ) -> GovernedSourceChannel:
        channel = self._channels.get(source_id)
        if channel is None:
            raise SourceRecordInputError("请选择系统已审核、且支持地点事实的来源渠道")
        if collection_mode not in channel.collection_modes:
            raise SourceRecordInputError("所选采集方式不适用于该来源渠道")
        parsed = urlsplit(source_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise SourceRecordInputError("具体来源地址必须是完整的 HTTPS 地址")
        if parsed.username or parsed.password:
            raise SourceRecordInputError("具体来源地址不能包含账号或密码")
        if parsed.fragment:
            raise SourceRecordInputError("具体来源地址不能包含页面片段标记")
        for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
            normalized = "".join(character for character in key.lower() if character.isalnum())
            if normalized in _SENSITIVE_QUERY_KEYS or normalized.endswith(
                ("key", "token", "secret", "password", "passwd", "signature", "sig")
            ):
                raise SourceRecordInputError("具体来源地址不能包含密钥、令牌或签名参数")
        if not any(_url_belongs_to(source_url, base_url) for base_url in channel.base_urls):
            raise SourceRecordInputError("具体来源地址不属于所选来源渠道的已审核域名")
        return channel

    def _build_channels(self) -> dict[str, GovernedSourceChannel]:
        registry_id = str(self._registry["registry_id"])
        dictionary_id = str(self._field_dictionary["dictionary_id"])
        channels: dict[str, GovernedSourceChannel] = {}
        raw_sources = self._registry.get("sources")
        if not isinstance(raw_sources, list):
            return channels
        for raw in raw_sources:
            if not isinstance(raw, dict):
                continue
            allowed_fields = tuple(str(item) for item in raw.get("allowed_fields", ()))
            if raw.get("review_status") != "reviewed":
                continue
            if raw.get("decision") not in {"approved", "conditional"}:
                continue
            if not any(field.startswith(_PLACE_FIELD_PREFIXES) for field in allowed_fields):
                continue
            channel = GovernedSourceChannel(
                source_id=str(raw["source_id"]),
                display_name=str(raw["display_name"]),
                source_kind=str(raw["source_kind"]),
                decision=str(raw["decision"]),
                collection_modes=tuple(str(item) for item in raw["collection_modes"]),
                base_urls=tuple(str(item) for item in raw["base_urls"]),
                conditions=tuple(str(item) for item in raw.get("conditions", ())),
                registry_id=registry_id,
                registry_sha256=self._registry_sha256,
                field_dictionary_id=dictionary_id,
                field_dictionary_sha256=self._field_dictionary_sha256,
            )
            channels[channel.source_id] = channel
        return channels


def _url_belongs_to(source_url: str, base_url: str) -> bool:
    source = urlsplit(source_url)
    base = urlsplit(base_url)
    if source.scheme.lower() != base.scheme.lower() or source.hostname != base.hostname:
        return False
    source_port = source.port or (443 if source.scheme.lower() == "https" else None)
    base_port = base.port or (443 if base.scheme.lower() == "https" else None)
    if source_port != base_port:
        return False
    base_path = base.path.rstrip("/")
    return not base_path or source.path == base_path or source.path.startswith(base_path + "/")
