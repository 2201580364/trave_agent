"""O05 time evidence routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from travel_agent.domain.admin import AdminPrincipal

from . import admin_responses as responses
from .admin import RetirePlaceEvidenceInput, _revision_response
from .admin_time_models import (
    GenerateHolidayExceptionsInput,
    PlaceClosureInput,
    PlaceDateExceptionInput,
    PlaceTimeRuleInput,
)


def register_o05_routes(router: APIRouter, review_workflow, principal_dependency) -> None:
    @router.post(
        "/place-revisions/{revision_id}/time-rules",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def create_place_time_rule(
        revision_id: str,
        payload: PlaceTimeRuleInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.create_time_rule(
            current,
            revision_id=revision_id,
            expected_revision_version=payload.expected_revision_version,
            rule_kind=payload.rule_kind,
            weekdays=payload.weekdays,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            last_entry_minute=payload.last_entry_minute,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.patch(
        "/place-revisions/{revision_id}/time-rules/{time_rule_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def update_place_time_rule(
        revision_id: str,
        time_rule_id: str,
        payload: PlaceTimeRuleInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.update_time_rule(
            current,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
            expected_revision_version=payload.expected_revision_version,
            rule_kind=payload.rule_kind,
            weekdays=payload.weekdays,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            last_entry_minute=payload.last_entry_minute,
            valid_from=payload.valid_from,
            valid_to=payload.valid_to,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/time-rules/{time_rule_id}/deletions",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def delete_place_time_rule(
        revision_id: str,
        time_rule_id: str,
        payload: RetirePlaceEvidenceInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.delete_time_rule(
            current,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
            expected_revision_version=payload.expected_revision_version,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.delete(
        "/place-revisions/{revision_id}/time-rules/{time_rule_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def retire_place_time_rule(
        revision_id: str,
        time_rule_id: str,
        payload: RetirePlaceEvidenceInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.retire_time_rule(
            current,
            revision_id=revision_id,
            time_rule_id=time_rule_id,
            expected_revision_version=payload.expected_revision_version,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/closures",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def create_place_closure(
        revision_id: str,
        payload: PlaceClosureInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.create_closure(
            current,
            revision_id=revision_id,
            expected_revision_version=payload.expected_revision_version,
            weekday=payload.weekday,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/holiday-exceptions",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def generate_holiday_exceptions(
        revision_id: str,
        payload: GenerateHolidayExceptionsInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.generate_holiday_exceptions(
            current,
            revision_id=revision_id,
            expected_revision_version=payload.expected_revision_version,
            calendar_id=payload.calendar_id,
            source_record_id=payload.source_record_id,
            open_start_minute=payload.open_start_minute,
            open_end_minute=payload.open_end_minute,
            open_last_entry_minute=payload.open_last_entry_minute,
            shift_closure=payload.shift_closure,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.patch(
        "/place-revisions/{revision_id}/closures/{closure_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def update_place_closure(
        revision_id: str,
        closure_id: str,
        payload: PlaceClosureInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.update_closure(
            current,
            revision_id=revision_id,
            closure_id=closure_id,
            expected_revision_version=payload.expected_revision_version,
            weekday=payload.weekday,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.delete(
        "/place-revisions/{revision_id}/closures/{closure_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def retire_place_closure(
        revision_id: str,
        closure_id: str,
        payload: RetirePlaceEvidenceInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.retire_closure(
            current,
            revision_id=revision_id,
            closure_id=closure_id,
            expected_revision_version=payload.expected_revision_version,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.post(
        "/place-revisions/{revision_id}/date-exceptions",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def create_place_date_exception(
        revision_id: str,
        payload: PlaceDateExceptionInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.create_date_exception(
            current,
            revision_id=revision_id,
            expected_revision_version=payload.expected_revision_version,
            service_date=payload.service_date,
            exception_kind=payload.exception_kind,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            last_entry_minute=payload.last_entry_minute,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.patch(
        "/place-revisions/{revision_id}/date-exceptions/{date_exception_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def update_place_date_exception(
        revision_id: str,
        date_exception_id: str,
        payload: PlaceDateExceptionInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.update_date_exception(
            current,
            revision_id=revision_id,
            date_exception_id=date_exception_id,
            expected_revision_version=payload.expected_revision_version,
            service_date=payload.service_date,
            exception_kind=payload.exception_kind,
            start_minute=payload.start_minute,
            end_minute=payload.end_minute,
            last_entry_minute=payload.last_entry_minute,
            source_record_id=payload.source_record_id,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)

    @router.delete(
        "/place-revisions/{revision_id}/date-exceptions/{date_exception_id}",
        response_model=responses.PlaceRevision,
        response_model_exclude_unset=True,
    )
    def retire_place_date_exception(
        revision_id: str,
        date_exception_id: str,
        payload: RetirePlaceEvidenceInput,
        request: Request,
        current: AdminPrincipal = principal_dependency,
    ) -> dict[str, object]:
        revision = review_workflow.retire_date_exception(
            current,
            revision_id=revision_id,
            date_exception_id=date_exception_id,
            expected_revision_version=payload.expected_revision_version,
            operation_intent_id=payload.operation_intent_id,
            reason_code=payload.reason_code,
            reason_text=payload.reason_text,
            request_id=request.state.request_id,
        )
        return _revision_response(revision)
