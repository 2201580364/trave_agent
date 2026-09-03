"""Restricted China Government Web announcement discovery and retrieval."""

from __future__ import annotations

import hashlib
import html
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx

from travel_agent.application.admin.holiday_calendar_sync import (
    OfficialHolidayAnnouncement,
    OfficialSourceTemporarilyUnavailable,
)

SEARCH_ENDPOINT = "https://sousuo.www.gov.cn/search-gov/data"
_TITLE_TAG = re.compile(r"<[^>]+>")


class GovCnAnnouncementDiscoverer:
    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def discover(self, *, year: int) -> OfficialHolidayAnnouncement | None:
        query = f"{year}年部分节假日安排"
        # The government search index often ranks a newer notice above a
        # historical one. Historical years therefore get an exact-title retry.
        queries = (
            (f"国务院办公厅关于{year}年部分节假日安排的通知", query)
            if year < datetime.now(UTC).year
            else (query,)
        )
        try:
            payloads = []
            for current_query in queries:
                response = self._client.get(
                    SEARCH_ENDPOINT,
                    params={"t": "zhengce", "q": current_query},
                    timeout=15.0,
                )
                response.raise_for_status()
                payloads.append(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise OfficialSourceTemporarilyUnavailable(
                "中国政府网公告搜索暂时不可用"
            ) from exc
        if any(payload.get("code") != 200 for payload in payloads):
            raise OfficialSourceTemporarilyUnavailable("中国政府网公告搜索返回异常状态")

        expected = f"国务院办公厅关于{year}年部分节假日安排的通知"
        matches: list[dict[str, Any]] = []
        for payload in payloads:
            for item in _search_items(payload):
                title = _plain_text(str(item.get("title") or ""))
                url = str(item.get("url") or "").strip()
                publisher = str(item.get("puborg") or "").strip()
                if title == expected and publisher == "国务院办公厅" and _official_url(url):
                    matches.append(item)
        if not matches:
            return None
        matches.sort(key=lambda item: str(item.get("pubtimeStr") or ""), reverse=True)
        selected = matches[0]
        url = str(selected["url"])
        published_at = _published_at(selected.get("pubtimeStr"))
        source_key = hashlib.sha256(
            f"{url}|{published_at.isoformat() if published_at else ''}".encode()
        ).hexdigest()[:20]
        return OfficialHolidayAnnouncement(
            url,
            expected,
            f"gov_cn_holiday_{year}_{source_key}",
            published_at,
        )


class GovCnAnnouncementFetcher:
    def __init__(self, client: httpx.Client, *, max_bytes: int = 5 * 1024 * 1024) -> None:
        self._client = client
        self._max_bytes = max_bytes

    def fetch(self, announcement: OfficialHolidayAnnouncement) -> bytes:
        if not _official_url(announcement.source_url):
            raise ValueError("official announcement URL is outside gov.cn")
        try:
            response = self._client.get(
                announcement.source_url,
                timeout=20.0,
                follow_redirects=True,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OfficialSourceTemporarilyUnavailable(
                "中国政府网公告页面暂时不可访问"
            ) from exc
        final_url = str(response.url)
        if not _official_url(final_url):
            raise ValueError("official announcement redirected outside gov.cn")
        content_type = response.headers.get("content-type", "").lower()
        if not any(item in content_type for item in ("text/html", "application/pdf")):
            raise ValueError("official announcement content type is unsupported")
        content = response.content
        if not content or len(content) > self._max_bytes:
            raise ValueError("official announcement content size is invalid")
        return content


def _search_items(payload: dict[str, Any]) -> tuple[dict[str, Any], ...]:
    search = payload.get("searchVO")
    if not isinstance(search, dict):
        return ()
    categories = search.get("catMap")
    if not isinstance(categories, dict):
        return ()
    result: list[dict[str, Any]] = []
    for category in categories.values():
        if not isinstance(category, dict):
            continue
        items = category.get("listVO")
        if isinstance(items, list):
            result.extend(item for item in items if isinstance(item, dict))
    return tuple(result)


def _plain_text(value: str) -> str:
    return "".join(html.unescape(_TITLE_TAG.sub("", value)).split())


def _official_url(value: str) -> bool:
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "gov.cn" or host.endswith(".gov.cn"))


def _published_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y.%m.%d").replace(tzinfo=UTC)
    except ValueError:
        return None
