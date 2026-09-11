"""Response contract slice: H3, API section 15, transformation-plan response models."""

from copy import deepcopy

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import ResponseValidationError

from tests.application.test_admin_identity_http import (
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_approvable_candidate,
)
from tests.application.test_admin_identity_http import (
    admin_context as admin_context,
)
from travel_agent.infrastructure.database.place_catalog import SqlAlchemyPlaceCatalogRepository
from travel_agent.interfaces.http import admin


def test_typed_detail_and_evidence_preserve_existing_wire_payload(admin_context: AdminTestContext):
    """No timestamp reformatting, lost nulls, new defaults, or dropped evidence fields."""
    _seed_approvable_candidate(admin_context)
    _, headers = _login(admin_context.client, ROOT_LOGIN, ROOT_PASSWORD)
    with admin_context.sessions() as session:
        evidence = SqlAlchemyPlaceCatalogRepository(session).load_revision_evidence("revision-1")
        assert evidence is not None
        expected_revision = jsonable_encoder(admin._revision_response(evidence.revision))
        expected_evidence = jsonable_encoder(admin._revision_evidence_response(evidence))
    base = "/api/v1/admin/place-revisions/revision-1"
    actual = admin_context.client.get(base, headers=headers)
    assert actual.status_code == 200
    assert actual.json() == expected_revision
    assert "review_readiness" not in actual.json()
    assert "published_at" in actual.json() and actual.json()["published_at"] is None
    actual = admin_context.client.get(base + "/evidence", headers=headers)
    assert actual.status_code == 200
    assert actual.json() == expected_evidence
    page = admin_context.client.get("/api/v1/admin/candidates", headers=headers)
    assert page.status_code == 200
    assert page.json()["items"][0]["review_readiness"]["total_checks"] == 6


@pytest.mark.parametrize("change", ["missing", "wrong_type", "unknown_enum", "unknown_field"])
def test_invalid_success_payload_is_rejected_instead_of_silently_published(
    admin_context: AdminTestContext,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
):
    """An HTTP handler drift must fail even when the underlying use case succeeds."""
    _seed_approvable_candidate(admin_context)
    _, headers = _login(admin_context.client, ROOT_LOGIN, ROOT_PASSWORD)
    serializer = admin._revision_response

    def broken(revision):
        result = deepcopy(serializer(revision))
        if change == "missing":
            result.pop("relation_review_status")
        elif change == "wrong_type":
            result["revision_version"] = "not-a-number"
        elif change == "unknown_enum":
            result["lifecycle_status"] = "unregistered-state"
        else:
            result["internal_debug_payload"] = "must-not-leak"
        return result

    monkeypatch.setattr(admin, "_revision_response", broken)
    with pytest.raises(ResponseValidationError):
        admin_context.client.get("/api/v1/admin/place-revisions/revision-1", headers=headers)


def test_openapi_exposes_nested_readiness_and_both_fixed_session_identifiers(
    admin_context: AdminTestContext,
):
    schema = admin_context.client.app.openapi()
    paths = schema["paths"]
    for path, model in (
        ("/place-revisions/{revision_id}", "PlaceRevision"),
        ("/place-revisions/{revision_id}/evidence", "PlaceRevisionEvidence"),
        ("/candidates", "PlaceRevisionPage"),
        ("/review-tasks", "ReviewTaskPage"),
        ("/review-tasks/{task_id}", "ReviewTask"),
        ("/place-revisions/{revision_id}/publication-checks", "PublicationCheck"),
        ("/place-revisions/{revision_id}/time-preview", "PlaceTimePreview"),
    ):
        response = paths["/api/v1/admin" + path]["get"]["responses"]["200"]
        assert response["content"]["application/json"]["schema"]["$ref"].endswith("/" + model)
    models = schema["components"]["schemas"]
    assert "review_readiness" in models["PlaceRevision"]["properties"]
    assert "checks" in models["ReviewReadiness"]["required"]
    assert "time_rule_id" in models["RegularSessionPreview"]["required"]
    assert "date_exception_id" in models["OverrideSessionPreview"]["required"]
    assert models["PlaceRevision"]["additionalProperties"] is False
