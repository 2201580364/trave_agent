"""Run an authorized stop/start recovery drill for Travel Agent MySQL and Redis."""

from __future__ import annotations

import os
import subprocess
import time
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from travel_agent.infrastructure.database.planning import TripDraftRow

MYSQL_CONTAINER = "travel-agent-mysql"
REDIS_CONTAINER = "travel-agent-redis"


def _docker(action: str, container: str) -> None:
    subprocess.run(
        ["docker", action, container],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _wait_for_mysql(engine, timeout_seconds: int = 90) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(select(1))
            return
        except SQLAlchemyError:
            time.sleep(1)
    raise AssertionError("MySQL did not recover before timeout")


def _wait_for_redis(client: Redis[str], timeout_seconds: int = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if client.ping():
                return
        except RedisError:
            pass
        time.sleep(1)
    raise AssertionError("Redis did not recover before timeout")


def main() -> None:
    mysql_url = os.environ.get("TRAVEL_AGENT_DATABASE_URL")
    redis_url = os.environ.get("TRAVEL_AGENT_PROVIDER_REDIS_URL")
    if not mysql_url or not redis_url:
        raise SystemExit("MySQL and Redis URLs are required")

    run_id = uuid.uuid4().hex[:12]
    draft_id = f"validation_recovery_draft_{run_id}"
    redis_key = f"travel-agent:validation:recovery:{run_id}"
    now = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    mysql_engine = create_engine(
        mysql_url,
        isolation_level="READ COMMITTED",
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    redis_client: Redis[str] = Redis.from_url(redis_url, decode_responses=True)

    mysql_stopped = False
    redis_stopped = False
    try:
        with Session(mysql_engine) as session:
            session.add(
                TripDraftRow(
                    draft_id=draft_id,
                    principal_id=f"validation_principal_{run_id}",
                    city_id="杭州",
                    draft_version=1,
                    status="editing",
                    travel_facts=None,
                    selected_attraction_ids=["断连恢复验证"],
                    visit_period_preferences=[],
                    created_at=now,
                    updated_at=now,
                )
            )
            session.commit()
        redis_client.set(redis_key, "persistent", ex=300)
        time.sleep(2)

        with mysql_engine.connect() as connection:
            connection.execute(select(1))
        _docker("stop", MYSQL_CONTAINER)
        mysql_stopped = True
        try:
            with mysql_engine.connect() as connection:
                connection.execute(select(1))
        except SQLAlchemyError:
            pass
        else:
            raise AssertionError("MySQL outage was not observed by the application engine")
        _docker("start", MYSQL_CONTAINER)
        mysql_stopped = False
        _wait_for_mysql(mysql_engine)
        with Session(mysql_engine) as session:
            restored_draft = session.get(TripDraftRow, draft_id)
            if restored_draft is None or restored_draft.city_id != "杭州":
                raise AssertionError("MySQL committed data did not survive restart")

        if not redis_client.ping():
            raise AssertionError("Redis was unavailable before recovery drill")
        _docker("stop", REDIS_CONTAINER)
        redis_stopped = True
        try:
            redis_client.ping()
        except RedisError:
            pass
        else:
            raise AssertionError("Redis outage was not observed by the application client")
        _docker("start", REDIS_CONTAINER)
        redis_stopped = False
        _wait_for_redis(redis_client)
        if redis_client.get(redis_key) != "persistent":
            raise AssertionError("Redis AOF/RDB data did not survive restart")

        print("Controlled service recovery validation passed.")
        print("MySQL outage was explicit; pool_pre_ping recovered after restart.")
        print("Committed MySQL data survived the container restart.")
        print("Redis outage was explicit; the client reconnected and data survived.")
    finally:
        if mysql_stopped:
            _docker("start", MYSQL_CONTAINER)
        if redis_stopped:
            _docker("start", REDIS_CONTAINER)
        _wait_for_mysql(mysql_engine)
        _wait_for_redis(redis_client)
        with Session(mysql_engine) as session:
            session.execute(delete(TripDraftRow).where(TripDraftRow.draft_id == draft_id))
            session.commit()
        redis_client.delete(redis_key)
        redis_client.close()
        mysql_engine.dispose()


if __name__ == "__main__":
    main()
