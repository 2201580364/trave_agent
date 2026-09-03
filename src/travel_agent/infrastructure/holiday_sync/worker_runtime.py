"""Environment-driven O17 worker process with bounded polling and file logs."""

from __future__ import annotations

import argparse
import logging
import signal
import threading
from pathlib import Path

import httpx

from travel_agent.application.admin.holiday_calendar_sync import (
    ChinaHolidayCalendarSyncService,
)
from travel_agent.application.admin.holiday_worker import HolidayCalendarSyncWorker
from travel_agent.infrastructure.database import (
    DatabaseReadiness,
    DatabaseSettings,
    SqlAlchemyHolidayCalendarUnitOfWork,
    build_engine,
    build_session_factory,
)
from travel_agent.infrastructure.ids import UuidIdGenerator
from travel_agent.infrastructure.memory import SystemClock
from travel_agent.observability import configure_file_logging

from .ai_extractor import AiHolidayAnnouncementExtractor
from .gov_cn import GovCnAnnouncementDiscoverer, GovCnAnnouncementFetcher
from .openai_compatible import HolidaySyncSettings, OpenAiCompatibleStructuredHolidayModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the China holiday calendar sync worker")
    parser.add_argument("--dotenv", type=Path, default=Path(".env"))
    parser.add_argument("--log-root", type=Path, default=Path("logs"))
    parser.add_argument("--once", action="store_true", help="Process one batch and exit")
    args = parser.parse_args()

    settings = HolidaySyncSettings.from_env(dotenv_path=args.dotenv)
    if not settings.configured:
        parser.error("holiday sync worker is disabled or its AI provider is incomplete")
    database = DatabaseSettings.from_env(load_dotenv_file=False)
    logger = configure_file_logging(
        args.log_root, component="holiday-worker", enable_console=False
    )
    engine = build_engine(database)
    sessions = build_session_factory(engine)
    readiness = DatabaseReadiness(sessions).check()
    if not readiness.get("ready"):
        raise RuntimeError(f"holiday worker database is not ready: {readiness}")

    with httpx.Client(headers={"User-Agent": "travel-agent-holiday-sync/1.0"}) as client:
        service = ChinaHolidayCalendarSyncService(
            lambda: SqlAlchemyHolidayCalendarUnitOfWork(sessions),
            SystemClock(),
            UuidIdGenerator(),
            GovCnAnnouncementDiscoverer(client),
            GovCnAnnouncementFetcher(client),
            AiHolidayAnnouncementExtractor(
                OpenAiCompatibleStructuredHolidayModel(
                    client,
                    base_url=settings.model_base_url,
                    api_key=settings.model_api_key,
                    model=settings.model_name,
                    timeout_seconds=settings.timeout_seconds,
                )
            ),
            worker_available=True,
        )
        worker = HolidayCalendarSyncWorker(service)
        if args.once:
            _run_batch(worker, settings.batch_size, logger)
            return
        _run_loop(worker, settings, logger)


def _run_loop(
    worker: HolidayCalendarSyncWorker,
    settings: HolidaySyncSettings,
    logger: logging.Logger,
) -> None:
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        logger.info("holiday calendar worker stop requested", extra={"signal": signum})
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    logger.info("holiday calendar worker started")
    while not stop.is_set():
        _run_batch(worker, settings.batch_size, logger)
        stop.wait(settings.poll_seconds)
    logger.info("holiday calendar worker stopped")


def _run_batch(
    worker: HolidayCalendarSyncWorker, batch_size: int, logger: logging.Logger
) -> None:
    result = worker.run_batch(max_jobs=batch_size)
    if result.processed_job_ids:
        logger.info(
            "holiday calendar worker batch completed",
            extra={"processed_count": len(result.processed_job_ids)},
        )
    if result.error_type:
        logger.error(
            "holiday calendar worker batch interrupted",
            extra={"error_type": result.error_type},
        )


if __name__ == "__main__":
    main()
