"""A6-6 anonymous HTTP vertical-slice tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import SolverOutcome
from travel_agent.domain.planning import CompletionKind
from travel_agent.infrastructure.database import (
    AnonymousIdentityService,
    SqlAlchemyUnitOfWork,
    create_schema,
)
from travel_agent.infrastructure.execution import InlineGenerationExecutor
from travel_agent.infrastructure.memory import (
    FixedDataSnapshotVersionProvider,
    SequenceIdGenerator,
)
from travel_agent.infrastructure.sharing import HmacPlanShareTokenCodec
from travel_agent.infrastructure.solver import (
    InMemoryPublishedSolverDataProvider,
    PublishedAttraction,
    PublishedSolverData,
)
from travel_agent.interfaces.http import HttpContainer, create_app
from travel_agent.solver import (
    Attraction,
    DailyWeather,
    InMemoryTravelTimeProvider,
    WeatherBasis,
    WeatherSeverity,
)

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


class SequenceTokenGenerator:
    def __init__(self) -> None:
        self._next = 1

    def new_token(self) -> str:
        token = f"anonymous-secret-{self._next}"
        self._next += 1
        return token


class FakeGateway:
    def solve(self, request: object) -> SolverOutcome:
        return SolverOutcome(
            CompletionKind.COMPLETE_SUCCESS,
            False,
            True,
            "trip-result-v1",
            {
                "schema_version": "trip-result-v1",
                "days": [{"date": "2026-09-01", "nodes": []}],
            },
            "b" * 64,
            "solver-p1-v1",
            "constraints-p1-v1",
            "parameters-p1-2026-08-24",
            {"solve_run_id": request.solver_run_id},
        )


def _client(tmp_path: Path) -> TestClient:
    engine = create_engine(f"sqlite:///{tmp_path / 'http.db'}")
    create_schema(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    ids = SequenceIdGenerator()
    clock = FixedClock()
    def uow_factory() -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(sessions)

    execute = ExecuteGenerationHandler(
        uow_factory(), clock, ids, FakeGateway()
    )
    identity = AnonymousIdentityService(
        sessions, clock, ids, SequenceTokenGenerator()
    )
    published = PublishedSolverData(
        "hangzhou-v1",
        "hangzhou",
        (
            PublishedAttraction(
                "attr_west_lake",
                Attraction(
                    1,
                    "西湖湖滨",
                    suggested_duration=90,
                    is_always_open=True,
                    energy_level=2,
                    data_verified=True,
                ),
            ),
            PublishedAttraction(
                "attr_museum",
                Attraction(
                    2,
                    "浙江省博物馆",
                    suggested_duration=120,
                    is_always_open=True,
                    energy_level=2,
                    data_verified=True,
                ),
            ),
        ),
        {
            NOW.date(): DailyWeather(
                NOW.date(), WeatherBasis.FORECAST, WeatherSeverity.NORMAL
            )
        },
        InMemoryTravelTimeProvider({}),
        "approximate",
        "forecast",
    )
    catalog = InMemoryPublishedSolverDataProvider((published,))
    container = HttpContainer(
        uow_factory,
        clock,
        ids,
        FixedDataSnapshotVersionProvider({"hangzhou": "hangzhou-v1"}),
        InlineGenerationExecutor(execute),
        identity,
        catalog,
        None,
        HmacPlanShareTokenCodec(
            "test-plan-share-secret-2026-08-28-at-least-32-bytes"
        ),
    )
    return TestClient(create_app(container))


def _session(client: TestClient) -> tuple[str, str]:
    response = client.post(
        "/api/v1/anonymous-sessions",
        json={"device_installation_id": "device_1"},
    )
    assert response.status_code == 201
    body = response.json()
    return body["principal_id"], body["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_anonymous_user_completes_http_planning_and_recovers_revision(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    principal_id, token = _session(client)
    headers = _auth(token)

    created = client.post(
        "/api/v1/trip-drafts", json={"city_id": "hangzhou"}, headers=headers
    )
    assert created.status_code == 201
    draft_id = created.json()["draft_id"]

    facts = client.patch(
        f"/api/v1/trip-drafts/{draft_id}/travel-facts",
        headers=headers,
        json={
            "expected_draft_version": 1,
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
            "arrival": {
                "transport_type": "already_in_destination",
                "confirmation": "confirmed",
                "arrives_at": "2026-09-01T09:00:00+08:00",
                "station_to_city_min": 0,
                "station_to_city_source": "not_applicable",
            },
            "departure": {
                "transport_type": "already_in_destination",
                "confirmation": "confirmed_by_inheritance",
                "departs_at": "2026-09-01T21:00:00+08:00",
                "station_early_min": 0,
                "station_early_source": "not_applicable",
                "last_visit_to_station_min": 0,
                "last_visit_to_station_source": "not_applicable",
            },
            "travel_mode": "normal",
            "crowd_type": "solo",
        },
    )
    assert facts.status_code == 200
    assert facts.json()["travel_facts"]["arrival"]["transport_type"] == (
        "already_in_destination"
    )

    selection = client.put(
        f"/api/v1/trip-drafts/{draft_id}/attraction-selection",
        headers=headers,
        json={
            "expected_draft_version": 2,
            "attraction_ids": ["attr_west_lake"],
            "visit_period_preferences": [],
        },
    )
    assert selection.status_code == 200

    review = client.get(f"/api/v1/trip-drafts/{draft_id}/review", headers=headers)
    assert review.json()["ready_for_generation"] is True

    generated = client.post(
        "/api/v1/generation-intents",
        headers=headers,
        json={
            "generation_intent_id": "intent_browser_1",
            "draft_id": draft_id,
            "draft_version": 3,
        },
    )
    assert generated.status_code == 202
    intent = generated.json()
    assert intent["status"] == "completed"
    assert intent["principal_id"] == principal_id

    trip = client.get(f"/api/v1/trips/{intent['trip_id']}", headers=headers)
    assert trip.status_code == 200
    assert trip.json()["current_revision_number"] == 1
    assert "principal_id" not in trip.json()
    assert "source_draft_id" not in trip.json()
    revision = client.get(
        f"/api/v1/trips/{intent['trip_id']}/revisions/{intent['trip_revision_id']}",
        headers=headers,
    )
    assert revision.status_code == 200
    assert revision.json()["result_snapshot"]["schema_version"] == "trip-result-v1"
    assert revision.headers["X-Request-ID"].startswith("req_")

    replacement = client.post(
        f"/api/v1/trips/{intent['trip_id']}/revisions/{intent['trip_revision_id']}"
        "/attraction-replacements",
        headers=headers,
        json={
            "generation_intent_id": "intent_browser_2",
            "old_attraction_id": "attr_west_lake",
            "new_attraction_id": "attr_museum",
        },
    )
    assert replacement.status_code == 202
    replacement_intent = replacement.json()
    assert replacement_intent["status"] == "completed"
    assert replacement_intent["trip_id"] == intent["trip_id"]
    assert replacement_intent["trip_revision_id"] != intent["trip_revision_id"]

    replacement_draft = client.get(
        f"/api/v1/trip-drafts/{replacement_intent['replacement_draft_id']}",
        headers=headers,
    )
    assert replacement_draft.json()["selected_attraction_ids"] == ["attr_museum"]
    latest_revision = client.get(
        f"/api/v1/trips/{intent['trip_id']}/revisions/"
        f"{replacement_intent['trip_revision_id']}",
        headers=headers,
    )
    assert latest_revision.json()["revision_number"] == 2
    assert client.get(
        f"/api/v1/trips/{intent['trip_id']}/revisions/{intent['trip_revision_id']}",
        headers=headers,
    ).status_code == 200

    repeated = client.post(
        f"/api/v1/trips/{intent['trip_id']}/revisions/{intent['trip_revision_id']}"
        "/attraction-replacements",
        headers=headers,
        json={
            "generation_intent_id": "intent_browser_2",
            "old_attraction_id": "attr_west_lake",
            "new_attraction_id": "attr_museum",
        },
    )
    assert repeated.status_code == 202
    assert repeated.json()["trip_revision_id"] == replacement_intent[
        "trip_revision_id"
    ]

    stale = client.post(
        f"/api/v1/trips/{intent['trip_id']}/revisions/{intent['trip_revision_id']}"
        "/attraction-replacements",
        headers=headers,
        json={
            "generation_intent_id": "intent_browser_stale",
            "old_attraction_id": "attr_west_lake",
            "new_attraction_id": "attr_museum",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "trip_revision_conflict"

    trips = client.get("/api/v1/trips?limit=20&offset=0", headers=headers)
    assert trips.status_code == 200
    assert trips.json()["has_more"] is False
    assert trips.json()["items"] == [
        {
            "trip_id": intent["trip_id"],
            "city_id": "hangzhou",
            "city_name": "杭州",
            "current_revision_id": replacement_intent["trip_revision_id"],
            "current_revision_number": 2,
            "completion_kind": "complete_success",
            "has_soft_degradation": False,
            "start_date": "2026-09-01",
            "end_date": "2026-09-01",
            "scheduled_count": 0,
            "unplaced_count": 0,
            "updated_at": NOW.isoformat(),
            "revision_count": 2,
        }
    ]

    revisions = client.get(
        f"/api/v1/trips/{intent['trip_id']}/revisions",
        headers=headers,
    )
    assert revisions.status_code == 200
    assert revisions.json()["current_revision_id"] == replacement_intent[
        "trip_revision_id"
    ]
    assert [item["revision_number"] for item in revisions.json()["items"]] == [
        2,
        1,
    ]
    assert [item["is_current"] for item in revisions.json()["items"]] == [
        True,
        False,
    ]

    share = client.post(
        f"/api/v1/trips/{intent['trip_id']}/plan-shares",
        headers=headers,
        json={
            "plan_share_intent_id": "share_intent_browser_1",
            "revision_id": replacement_intent["trip_revision_id"],
            "template": "simple",
        },
    )
    assert share.status_code == 201
    share_body = share.json()
    assert share_body["status"] == "published"
    assert share_body["reused"] is False
    assert share_body["share_path"].endswith(share_body["share_token"])
    assert "principal_id" not in share.text
    assert "source_draft_id" not in share.text

    public = client.get(f"/api/v1/plan-shares/{share_body['share_token']}")
    assert public.status_code == 200
    assert public.headers["Cache-Control"] == "no-store"
    assert public.json()["content"]["content_kind"] == "planned_itinerary"
    assert "share_token" not in public.text
    assert "principal_id" not in public.text

    repeated_share = client.post(
        f"/api/v1/trips/{intent['trip_id']}/plan-shares",
        headers=headers,
        json={
            "plan_share_intent_id": "share_intent_browser_1",
            "revision_id": replacement_intent["trip_revision_id"],
            "template": "simple",
        },
    )
    assert repeated_share.status_code == 201
    assert repeated_share.json()["reused"] is True
    assert repeated_share.json()["share_token"] == share_body["share_token"]

    _, visitor_token = _session(client)
    visitor_headers = _auth(visitor_token)
    copied = client.post(
        f"/api/v1/plan-shares/{share_body['share_token']}/draft-copies",
        headers=visitor_headers,
    )
    assert copied.status_code == 201
    assert copied.json()["selected_attraction_ids"] == ["attr_museum"]
    assert copied.json()["travel_facts"] is None
    assert client.get(
        f"/api/v1/trip-drafts/{copied.json()['draft_id']}",
        headers=headers,
    ).status_code == 404
    assert client.get("/api/v1/plan-shares/not-a-valid-token").status_code == 404


def test_anonymous_ownership_is_hidden_as_not_found(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, first_token = _session(client)
    _, second_token = _session(client)
    created = client.post(
        "/api/v1/trip-drafts",
        json={"city_id": "hangzhou"},
        headers=_auth(first_token),
    )

    response = client.get(
        f"/api/v1/trip-drafts/{created.json()['draft_id']}",
        headers=_auth(second_token),
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "resource_not_found"
    assert client.get("/api/v1/trips", headers=_auth(second_token)).json()[
        "items"
    ] == []


def test_draft_conflict_uses_stable_error_and_request_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, token = _session(client)
    headers = {**_auth(token), "X-Request-ID": "req_client_123"}
    created = client.post(
        "/api/v1/trip-drafts", json={"city_id": "hangzhou"}, headers=headers
    )
    draft_id = created.json()["draft_id"]

    response = client.put(
        f"/api/v1/trip-drafts/{draft_id}/attraction-selection",
        headers=headers,
        json={"expected_draft_version": 99, "attraction_ids": ["attr_1"]},
    )

    assert response.status_code == 409
    assert response.headers["X-Request-ID"] == "req_client_123"
    assert response.json()["error"]["code"] == "draft_version_conflict"


def test_auth_validation_and_readiness_use_http_contract(tmp_path: Path) -> None:
    client = _client(tmp_path)

    ready = client.get("/health/ready")
    unauthorized = client.post("/api/v1/trip-drafts", json={"city_id": "hangzhou"})
    invalid = client.post(
        "/api/v1/anonymous-sessions",
        json={"device_installation_id": "x" * 129},
    )

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["database"] is True
    assert unauthorized.status_code == 401
    assert unauthorized.json()["error"]["code"] == "authentication_required"
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "request_validation_failed"
    assert invalid.json()["error"]["field_errors"][0]["field"] == (
        "device_installation_id"
    )


def test_domain_validation_failure_does_not_expose_stack_trace(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, token = _session(client)
    headers = _auth(token)
    created = client.post(
        "/api/v1/trip-drafts", json={"city_id": "hangzhou"}, headers=headers
    )

    response = client.patch(
        f"/api/v1/trip-drafts/{created.json()['draft_id']}/travel-facts",
        headers=headers,
        json={
            "expected_draft_version": 1,
            "start_date": "2026-09-02",
            "end_date": "2026-09-01",
            "arrival": {
                "transport_type": "already_in_destination",
                "confirmation": "confirmed",
                "arrives_at": "2026-09-02T09:00:00+08:00",
                "station_to_city_min": 0,
                "station_to_city_source": "not_applicable",
            },
            "departure": {
                "transport_type": "already_in_destination",
                "confirmation": "confirmed_by_inheritance",
                "departs_at": "2026-09-02T21:00:00+08:00",
                "station_early_min": 0,
                "station_early_source": "not_applicable",
                "last_visit_to_station_min": 0,
                "last_visit_to_station_source": "not_applicable",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "domain_validation_failed"
    assert "traceback" not in response.text.lower()


def test_catalog_uses_published_snapshot_and_external_ids(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _, token = _session(client)

    listing = client.get("/api/v1/attractions", headers=_auth(token))
    detail = client.get(
        "/api/v1/attractions/attr_west_lake", headers=_auth(token)
    )

    assert listing.status_code == 200
    assert listing.json()["data_snapshot_version"] == "hangzhou-v1"
    assert listing.json()["items"][0]["attraction_id"] == "attr_west_lake"
    assert detail.status_code == 200
    assert detail.json()["name"] == "西湖湖滨"
