"""O05 time evidence request models."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PlaceTimeRuleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    rule_kind: str = Field(pattern="^(opening_hours|fixed_session|last_entry)$")
    weekdays: tuple[int, ...] = Field(min_length=1, max_length=7)
    start_minute: int | None = Field(default=None, ge=0, le=2880)
    end_minute: int | None = Field(default=None, ge=0, le=2880)
    last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    valid_from: date | None = None
    valid_to: date | None = None
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceClosureInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    weekday: int = Field(ge=1, le=7)
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class PlaceDateExceptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision_version: int = Field(gt=0)
    service_date: date
    exception_kind: str = Field(pattern="^(closed|open_override|session_override)$")
    start_minute: int | None = Field(default=None, ge=0, le=2880)
    end_minute: int | None = Field(default=None, ge=0, le=2880)
    last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    source_record_id: str = Field(min_length=1, max_length=64)
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)


class GenerateHolidayExceptionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision_version: int = Field(gt=0)
    calendar_id: str = Field(min_length=1, max_length=64)
    source_record_id: str = Field(default="", max_length=64)
    open_start_minute: int = Field(ge=0, le=2880)
    open_end_minute: int = Field(ge=0, le=2880)
    open_last_entry_minute: int | None = Field(default=None, ge=0, le=2880)
    shift_closure: bool = True
    operation_intent_id: str = Field(min_length=1, max_length=64)
    reason_code: str = Field(min_length=3, max_length=64)
    reason_text: str | None = Field(default=None, max_length=500)
