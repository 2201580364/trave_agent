from __future__ import annotations

import httpx
import pytest

from travel_agent.application.admin.holiday_calendar_sync import (
    OfficialHolidayAnnouncement,
    OfficialSourceTemporarilyUnavailable,
)
from travel_agent.infrastructure.holiday_sync import (
    GovCnAnnouncementDiscoverer,
    GovCnAnnouncementFetcher,
)


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_discoverer_accepts_only_exact_state_council_office_notice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["q"] == "2027年部分节假日安排"
        return httpx.Response(
            200,
            json={
                "code": 200,
                "searchVO": {
                    "catMap": {
                        "gongwen": {
                            "listVO": [
                                {
                                    "title": "国务院办公厅关于<em>2027</em>年部分节假日安排的通知",
                                    "url": "https://www.gov.cn/zhengce/content/202611/holiday.htm",
                                    "puborg": "国务院办公厅",
                                    "pubtimeStr": "2026.11.05",
                                },
                                {
                                    "title": "2027年部分节假日安排解读",
                                    "url": "https://example.com/repost",
                                    "puborg": "其他机构",
                                    "pubtimeStr": "2026.11.06",
                                },
                            ]
                        }
                    }
                },
            },
        )

    announcement = GovCnAnnouncementDiscoverer(_client(handler)).discover(year=2027)

    assert announcement is not None
    assert announcement.source_url.startswith("https://www.gov.cn/")
    assert announcement.source_record_id.startswith("gov_cn_holiday_2027_")


def test_discoverer_returns_not_found_only_after_successful_official_search() -> None:
    client = _client(
        lambda request: httpx.Response(
            200, json={"code": 200, "searchVO": {"catMap": {}}}
        )
    )

    assert GovCnAnnouncementDiscoverer(client).discover(year=2027) is None


def test_discovery_network_failure_is_temporary_unavailability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(OfficialSourceTemporarilyUnavailable):
        GovCnAnnouncementDiscoverer(_client(handler)).discover(year=2027)


def test_fetcher_rejects_official_redirect_to_external_domain() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "www.gov.cn":
            return httpx.Response(302, headers={"location": "https://example.com/file"})
        return httpx.Response(200, headers={"content-type": "text/html"}, content=b"bad")

    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/holiday", "notice", "source"
    )
    with pytest.raises(ValueError, match="redirected outside"):
        GovCnAnnouncementFetcher(_client(handler)).fetch(announcement)


def test_fetcher_accepts_bounded_official_html() -> None:
    client = _client(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            content="国务院办公厅节假日通知".encode(),
        )
    )
    announcement = OfficialHolidayAnnouncement(
        "https://www.gov.cn/holiday", "notice", "source"
    )

    assert GovCnAnnouncementFetcher(client).fetch(announcement)
