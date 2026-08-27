"""Run destructive-but-self-cleaning persistence checks against authorized MySQL.

The database URL is read from ``TRAVEL_AGENT_DATABASE_URL`` and is never printed.
This script is intended for an isolated validation database or an explicitly
authorized deployment database during a controlled release check.
"""

from __future__ import annotations

import os
import threading
import uuid
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from travel_agent.domain.planning import (
    ConfirmationStatus,
    CrowdType,
    GenerationIntent,
    GenerationStatus,
    TransportType,
    TravelFacts,
    TravelMode,
    Trip,
    TripDraft,
)
from travel_agent.infrastructure.database import SqlAlchemyUnitOfWork
from travel_agent.infrastructure.database.planning import (
    GenerationIntentRow,
    TripDraftRow,
    TripRow,
)


def main() -> None:
    database_url = os.environ.get("TRAVEL_AGENT_DATABASE_URL")
    if not database_url:
        raise SystemExit("TRAVEL_AGENT_DATABASE_URL is required")

    run_id = uuid.uuid4().hex[:12]
    principal_id = f"validation_principal_{run_id}"
    draft_id = f"validation_draft_{run_id}"
    intent_id = f"validation_intent_{run_id}"
    rollback_trip_id = f"validation_rollback_trip_{run_id}"
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime(2026, 8, 28, 21, 0, tzinfo=timezone)

    engine = create_engine(
        database_url,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        pool_size=4,
        max_overflow=0,
    )
    session_factory = sessionmaker(engine, expire_on_commit=False)

    draft = TripDraft.create(
        draft_id=draft_id,
        principal_id=principal_id,
        city_id="杭州",
        now=now,
    )
    facts = TravelFacts(
        start_date=date(2026, 8, 28),
        end_date=date(2026, 8, 29),
        arrival_transport_type=TransportType.HIGH_SPEED_RAIL,
        arrival_confirmation=ConfirmationStatus.CONFIRMED,
        arrival_at=datetime(2026, 8, 28, 21, 30, tzinfo=timezone),
        station_to_city_min=45,
        station_to_city_source="高德真实路网🚄",
        departure_transport_type=TransportType.HIGH_SPEED_RAIL,
        departure_confirmation=ConfirmationStatus.CONFIRMED_BY_INHERITANCE,
        departure_at=datetime(2026, 8, 29, 1, 30, tzinfo=timezone),
        station_early_min=30,
        station_early_source="产品规则",
        last_visit_to_station_min=20,
        last_visit_to_station_source="人工校验",
        travel_mode=TravelMode.LEISURE,
        crowd_type=CrowdType.FRIENDS,
    )
    draft = draft.update_travel_facts(facts, now=now)
    draft = draft.replace_selection(("西湖🌅", "浙江省博物馆"), (), now=now)
    intent = GenerationIntent(
        generation_intent_id=intent_id,
        principal_id=principal_id,
        draft_id=draft_id,
        draft_version=draft.draft_version,
        status=GenerationStatus.QUEUED,
        input_schema_version="generation-input-v1",
        input_snapshot={
            "city": "杭州",
            "note": "中文、emoji 与跨午夜 JSON 验证 🌙",
            "cross_midnight": {"arrival": "21:30+08:00", "departure": "01:30+08:00"},
            "attractions": ["西湖🌅", "浙江省博物馆"],
        },
        input_snapshot_hash="a" * 64,
        data_snapshot_version="validation-human-verified-v1",
        random_seed=20260828,
        submitted_at=now,
        updated_at=now,
    )

    try:
        with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
            unit_of_work.drafts.save(draft)
            unit_of_work.generation_intents.add(intent)
            unit_of_work.commit()

        engine.dispose()
        restart_engine = create_engine(
            database_url,
            isolation_level="READ COMMITTED",
            pool_pre_ping=True,
        )
        restart_factory = sessionmaker(restart_engine, expire_on_commit=False)
        with SqlAlchemyUnitOfWork(restart_factory) as unit_of_work:
            restored_draft = unit_of_work.drafts.get(draft_id)
            restored_intent = unit_of_work.generation_intents.get(intent_id)
        if restored_draft != draft or restored_intent != intent:
            raise AssertionError("MySQL restart read did not preserve domain values")
        restart_engine.dispose()

        barrier = threading.Barrier(2)
        claim_results: list[str] = []
        result_lock = threading.Lock()

        def claim_intent() -> None:
            result = "unexpected"
            try:
                with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
                    current = unit_of_work.generation_intents.get(intent_id)
                    if current is None:
                        raise AssertionError("validation intent disappeared")
                    claimed = current.claim_running(now=now)
                    barrier.wait(timeout=10)
                    unit_of_work.generation_intents.save(
                        claimed,
                        expected_status=GenerationStatus.QUEUED.value,
                    )
                    unit_of_work.commit()
                    result = "claimed"
            except ValueError as exc:
                if "status conflict" not in str(exc):
                    raise
                result = "conflict"
            finally:
                with result_lock:
                    claim_results.append(result)

        workers = [threading.Thread(target=claim_intent) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)
        if any(worker.is_alive() for worker in workers):
            raise AssertionError("concurrent claim worker did not finish")
        if sorted(claim_results) != ["claimed", "conflict"]:
            raise AssertionError(f"unexpected concurrent claim results: {claim_results}")

        rollback_trip = Trip(
            rollback_trip_id,
            principal_id,
            "杭州",
            draft_id,
            f"validation_revision_{run_id}",
            now,
            now,
        )
        try:
            with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
                unit_of_work.trips.add(rollback_trip)
                raise RuntimeError("intentional rollback validation")
        except RuntimeError as exc:
            if str(exc) != "intentional rollback validation":
                raise
        with SqlAlchemyUnitOfWork(session_factory) as unit_of_work:
            if unit_of_work.trips.get(rollback_trip_id) is not None:
                raise AssertionError("uncommitted transaction was not rolled back")

        print("MySQL persistence validation passed.")
        print("Chinese/emoji/JSON/cross-midnight timezone round trip passed.")
        print("Two-connection intent claim produced exactly one winner.")
        print("Intentional transaction failure rolled back without residue.")
    finally:
        with session_factory() as session:
            session.execute(
                delete(GenerationIntentRow).where(
                    GenerationIntentRow.generation_intent_id == intent_id
                )
            )
            session.execute(delete(TripRow).where(TripRow.trip_id == rollback_trip_id))
            session.execute(delete(TripDraftRow).where(TripDraftRow.draft_id == draft_id))
            session.commit()
        engine.dispose()


if __name__ == "__main__":
    main()
