"""Configurable OpenAI-compatible structured model for O17 extraction.

The adapter only returns a candidate structure. Source grounding and all
publication decisions remain in the deterministic domain/application layers.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from os import PathLike
from typing import Any

import httpx

from travel_agent.application.admin.holiday_calendar_sync import (
    HolidayExtractionError,
    HolidayExtractionTemporarilyUnavailable,
)
from travel_agent.runtime_config import load_runtime_environment


@dataclass(frozen=True, slots=True)
class HolidaySyncSettings:
    worker_enabled: bool = False
    model_base_url: str = "https://api.openai.com/v1"
    model_name: str = ""
    model_api_key: str = field(default="", repr=False)
    timeout_seconds: float = 300.0
    poll_seconds: float = 10.0
    batch_size: int = 10

    @property
    def configured(self) -> bool:
        return bool(self.worker_enabled and self.model_name and self.model_api_key)

    @classmethod
    def from_env(
        cls,
        *,
        dotenv_path: str | PathLike[str] | None = None,
        load_dotenv_file: bool = True,
    ) -> HolidaySyncSettings:
        if load_dotenv_file:
            load_runtime_environment(dotenv_path)
        enabled = os.environ.get("TRAVEL_AGENT_HOLIDAY_SYNC_WORKER_ENABLED", "false")
        timeout = float(os.environ.get("TRAVEL_AGENT_HOLIDAY_AI_TIMEOUT_SECONDS", "300"))
        poll = float(os.environ.get("TRAVEL_AGENT_HOLIDAY_WORKER_POLL_SECONDS", "10"))
        batch = int(os.environ.get("TRAVEL_AGENT_HOLIDAY_WORKER_BATCH_SIZE", "10"))
        settings = cls(
            worker_enabled=enabled.strip().lower() in {"1", "true", "yes", "on"},
            model_base_url=os.environ.get(
                "TRAVEL_AGENT_HOLIDAY_AI_BASE_URL", "https://api.openai.com/v1"
            ).rstrip("/"),
            model_name=os.environ.get("TRAVEL_AGENT_HOLIDAY_AI_MODEL", "").strip(),
            model_api_key=os.environ.get("TRAVEL_AGENT_HOLIDAY_AI_API_KEY", "").strip(),
            timeout_seconds=timeout,
            poll_seconds=poll,
            batch_size=batch,
        )
        if settings.worker_enabled and not settings.configured:
            raise ValueError(
                "holiday sync worker requires TRAVEL_AGENT_HOLIDAY_AI_MODEL and "
                "TRAVEL_AGENT_HOLIDAY_AI_API_KEY"
            )
        if timeout <= 0 or poll <= 0 or not 1 <= batch <= 100:
            raise ValueError("holiday sync worker timing or batch settings are invalid")
        return settings


class OpenAiCompatibleStructuredHolidayModel:
    """Call a chat-completions compatible endpoint and require one JSON object."""

    def __init__(
        self,
        client: httpx.Client,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 45.0,
    ) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds

    def extract_holiday_calendar(
        self, *, year: int, source_title: str, source_text: str
    ) -> dict[str, Any]:
        schema = {
            "region": "CN",
            "year": year,
            "periods": [
                {
                    "name": "元旦/春节/清明节/劳动节/端午节/中秋节/国庆节",
                    "start": "YYYY-MM-DD",
                    "end": "YYYY-MM-DD",
                    "evidence_quote": "公告原文中的连续文本片段",
                }
            ],
            "adjusted_workdays": [
                {
                    "date": "YYYY-MM-DD",
                    "holiday_name": "对应节日",
                    "evidence_quote": "公告原文中的连续文本片段",
                }
            ],
        }
        try:
            response = self._client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "你是中国法定节假日公告结构化工具。只能依据所给官方原文，"
                                "不得推测或补全。严格返回一个 JSON 对象，不要 Markdown。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"目标年份：{year}\n公告标题：{source_title}\n"
                                f"输出结构示例：{json.dumps(schema, ensure_ascii=False)}\n"
                                f"所有 periods.start、periods.end 和 adjusted_workdays.date "
                                f"必须属于 {year} 年；公告中的上班日期也只能按公告明确写出的 "
                                f"{year} 年日期填写。\n"
                                "每个 evidence_quote 必须逐字来自下方原文。\n官方原文：\n"
                                f"{source_text}"
                            ),
                        },
                    ],
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (httpx.HTTPError, ValueError) as exc:
            raise HolidayExtractionTemporarilyUnavailable(
                "AI 结构化服务暂时不可用"
            ) from exc
        except (KeyError, IndexError, TypeError) as exc:
            raise HolidayExtractionError("AI 服务响应缺少结构化结果") from exc
        if not isinstance(content, str):
            raise HolidayExtractionError("AI 服务响应内容格式无效")
        try:
            result = _parse_json_content(content)
        except json.JSONDecodeError as exc:
            raise HolidayExtractionError("AI 服务未返回有效 JSON") from exc
        if not isinstance(result, dict):
            raise HolidayExtractionError("AI 服务返回结果必须是对象")
        return result


def _parse_json_content(content: str) -> Any:
    """Accept strict JSON plus the common markdown fence wrapper."""
    value = content.strip()
    if value.startswith("```") and value.endswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*```$", "", value)
    return json.loads(value)
