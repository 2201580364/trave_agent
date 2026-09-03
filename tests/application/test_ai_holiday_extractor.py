from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from travel_agent.application.admin.holiday_calendar_sync import (
    HolidayExtractionError,
    OfficialHolidayAnnouncement,
)
from travel_agent.infrastructure.holiday_sync import (
    AiHolidayAnnouncementExtractor,
    HolidaySyncSettings,
    OpenAiCompatibleStructuredHolidayModel,
)

SOURCE = """
<html><body>
<p>一、元旦：1月1日放假。</p>
<p>二、春节：2月1日至2月7日放假调休。1月31日上班。</p>
</body></html>
""".encode()


class Model:
    def __init__(self, quote: str = "春节：2月1日至2月7日放假调休。") -> None:
        self.quote = quote

    def extract_holiday_calendar(self, *, year, source_title, source_text):
        assert "春节" in source_text
        return {
            "region": "CN",
            "year": year,
            "periods": [
                {
                    "name": "春节",
                    "start": f"{year}-02-01",
                    "end": f"{year}-02-07",
                    "evidence_quote": self.quote,
                }
            ],
            "adjusted_workdays": [
                {
                    "date": f"{year}-01-31",
                    "holiday_name": "春节",
                    "evidence_quote": "1月31日上班。",
                }
            ],
        }


def _extract(model: Model):
    return AiHolidayAnnouncementExtractor(model).extract(
        announcement=OfficialHolidayAnnouncement(
            "https://www.gov.cn/holiday",
            "国务院办公厅关于2027年部分节假日安排的通知",
            "source-2027",
        ),
        content=SOURCE,
        content_sha256=hashlib.sha256(SOURCE).hexdigest(),
        year=2027,
    )


def test_ai_extractor_maps_restricted_schema_and_grounded_quotes() -> None:
    result = _extract(Model())

    assert result.region_code == "CN"
    assert result.periods[0].name == "春节"
    assert result.adjusted_workdays[0].service_date.isoformat() == "2027-01-31"


def test_ai_extractor_rejects_quote_not_present_in_official_source() -> None:
    with pytest.raises(HolidayExtractionError, match="受限格式"):
        _extract(Model("模型自行补充的公告内容"))


def test_openai_compatible_model_requests_json_and_parses_candidate() -> None:
    expected = {"region": "CN", "year": 2027, "periods": [], "adjusted_workdays": []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer test-secret"
        body = json.loads(request.content)
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(expected)}}]},
        )

    model = OpenAiCompatibleStructuredHolidayModel(
        httpx.Client(transport=httpx.MockTransport(handler)),
        base_url="https://model.example/v1",
        api_key="test-secret",
        model="structured-test",
    )

    assert model.extract_holiday_calendar(
        year=2027, source_title="notice", source_text="official text"
    ) == expected


def test_holiday_sync_settings_require_complete_provider_when_worker_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRAVEL_AGENT_HOLIDAY_SYNC_WORKER_ENABLED", "true")
    monkeypatch.delenv("TRAVEL_AGENT_HOLIDAY_AI_MODEL", raising=False)
    monkeypatch.delenv("TRAVEL_AGENT_HOLIDAY_AI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="requires"):
        HolidaySyncSettings.from_env(load_dotenv_file=False)
