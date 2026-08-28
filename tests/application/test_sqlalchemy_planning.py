"""A6-5 SQLAlchemy persistence and recovery tests."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from travel_agent.application.common.errors import (
    DraftVersionConflictError,
    TripRevisionConflictError,
)
from travel_agent.application.planning import ExecuteGenerationHandler
from travel_agent.application.planning.ports import SolverOutcome, SolverRequest
from travel_agent.domain.planning import (
    CompletionKind,
    GenerationIntent,
    GenerationStatus,
    Trip,
    TripDraft,
)
from travel_agent.infrastructure.database import SqlAlchemyUnitOfWork, create_schema
from travel_agent.infrastructure.memory import SequenceIdGenerator

NOW = datetime(2026, 8, 24, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai"))


class FixedClock:
    def now(self) -> datetime:
        return NOW


class FakeGateway:
    def solve(self, request: SolverRequest) -> SolverOutcome:
        return SolverOutcome(
            CompletionKind.COMPLETE_SUCCESS,
            False,
            True,
            "trip-result-v1",
            {"schema_version": "trip-result-v1", "days": []},
            "b" * 64,
            "solver-p1-v1",
            "constraints-p1-v1",
            "parameters-p1-2026-08-24",
            {"solve_run_id": request.solver_run_id},
        )


def _factory(path: Path):
    engine = create_engine(f"sqlite:///{path}")
    create_schema(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _draft() -> TripDraft:
    return TripDraft.create(
        draft_id="draft_1", principal_id="principal_1", city_id="hangzhou", now=NOW
    )


def _intent() -> GenerationIntent:
    return GenerationIntent(
        "intent_1", "principal_1", "draft_1", 1, GenerationStatus.QUEUED,
        "generation-input-v1", {"city_id": "hangzhou"}, "a" * 64,
        "hangzhou-v1", 7, NOW, NOW,
    )


def test_draft_and_intent_survive_new_unit_of_work_and_engine(tmp_path: Path) -> None:
    database = tmp_path / "planning.db"
    factory = _factory(database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(_draft())
        uow.generation_intents.add(_intent())
        uow.commit()

    restarted_factory = _factory(database)
    with SqlAlchemyUnitOfWork(restarted_factory) as uow:
        restored_draft = uow.drafts.get("draft_1")
        restored_intent = uow.generation_intents.get("intent_1")

    assert restored_draft == _draft()
    assert restored_intent == _intent()


def test_draft_optimistic_lock_rejects_stale_database_update(tmp_path: Path) -> None:
    factory = _factory(tmp_path / "planning.db")
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(_draft())
        uow.commit()

    updated = _draft().replace_selection(("attr_1",), (), now=NOW)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(updated, expected_version=1)
        uow.commit()

    with SqlAlchemyUnitOfWork(factory) as uow, pytest.raises(DraftVersionConflictError):
        uow.drafts.save(updated, expected_version=1)


def test_intent_status_compare_and_swap_allows_only_one_claim(tmp_path: Path) -> None:
    factory = _factory(tmp_path / "planning.db")
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(_draft())
        uow.generation_intents.add(_intent())
        uow.commit()

    claimed = _intent().claim_running(now=NOW)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.generation_intents.save(claimed, expected_status="queued")
        uow.commit()

    with SqlAlchemyUnitOfWork(factory) as uow, pytest.raises(
        ValueError, match="status conflict"
    ):
        uow.generation_intents.save(claimed, expected_status="queued")


def test_trip_revision_compare_and_swap_rejects_stale_publisher(
    tmp_path: Path,
) -> None:
    factory = _factory(tmp_path / "planning.db")
    original = Trip(
        "trip_1", "principal_1", "hangzhou", "draft_1", "revision_1", NOW, NOW
    )
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.trips.add(original)
        uow.commit()

    first = SqlAlchemyUnitOfWork(factory)
    second = SqlAlchemyUnitOfWork(factory)
    with first as first_uow, second as second_uow:
        first_trip = first_uow.trips.get("trip_1")
        second_trip = second_uow.trips.get("trip_1")
        assert first_trip is not None and second_trip is not None
        first_uow.trips.save(
            first_trip.advance_revision(
                expected_revision_id="revision_1",
                new_revision_id="revision_2",
                now=NOW,
            ),
            expected_revision_id="revision_1",
        )
        first_uow.commit()

        with pytest.raises(TripRevisionConflictError):
            second_uow.trips.save(
                second_trip.advance_revision(
                    expected_revision_id="revision_1",
                    new_revision_id="revision_3",
                    now=NOW,
                ),
                expected_revision_id="revision_1",
            )


def test_uncommitted_completion_products_are_rolled_back(tmp_path: Path) -> None:
    factory = _factory(tmp_path / "planning.db")
    trip = Trip("trip_1", "principal_1", "hangzhou", "draft_1", "revision_1", NOW, NOW)

    with pytest.raises(RuntimeError, match="simulate failure"), SqlAlchemyUnitOfWork(
        factory
    ) as uow:
        uow.trips.add(trip)
        raise RuntimeError("simulate failure")

    with SqlAlchemyUnitOfWork(factory) as uow:
        assert uow.trips.get("trip_1") is None


def test_execute_generation_persists_complete_graph_across_restart(tmp_path: Path) -> None:
    database = tmp_path / "planning.db"
    factory = _factory(database)
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(_draft())
        uow.generation_intents.add(_intent())
        uow.commit()

    result = ExecuteGenerationHandler(
        SqlAlchemyUnitOfWork(factory),
        FixedClock(),
        SequenceIdGenerator(),
        FakeGateway(),
    ).handle("intent_1")

    restarted_factory = _factory(database)
    with SqlAlchemyUnitOfWork(restarted_factory) as uow:
        intent = uow.generation_intents.get("intent_1")
        trip = uow.trips.get(result.trip_id)
        revision = uow.trip_revisions.get(result.trip_revision_id)
        run = uow.solver_runs.get(result.solver_run_id)

    assert intent is not None and intent.status is GenerationStatus.COMPLETED
    assert trip is not None and trip.current_revision_id == result.trip_revision_id
    assert revision is not None and revision.result_snapshot["days"] == []
    assert run is not None and run.audit_payload["solve_run_id"] == result.solver_run_id


def test_alembic_upgrade_builds_the_same_schema(tmp_path: Path) -> None:
    database = tmp_path / "migrated.db"
    config = Config("alembic.ini")
    config.attributes["skip_dotenv"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")

    command.upgrade(config, "head")

    factory = sessionmaker(
        create_engine(f"sqlite:///{database}"), expire_on_commit=False
    )
    with SqlAlchemyUnitOfWork(factory) as uow:
        uow.drafts.save(_draft())
        uow.commit()
