"""Environment-driven durable worker for submitted itinerary generation."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import cast

from fastapi import FastAPI

from travel_agent.application.common.clock import Clock
from travel_agent.application.common.unit_of_work import UnitOfWork
from travel_agent.application.planning.worker import GenerationHandler, GenerationWorker
from travel_agent.infrastructure.generation.worker_runtime import env_int, run_batch, run_loop
from travel_agent.observability import configure_file_logging

from .http import ProductionHttpSettings, build_production_http_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable itinerary generation worker")
    parser.add_argument("--log-root", type=Path, default=Path("logs"))
    parser.add_argument("--once", action="store_true", help="Process one bounded batch and exit")
    args = parser.parse_args()
    app = build_production_http_app(ProductionHttpSettings.from_env())
    worker = _worker_from_app(app)
    logger = configure_file_logging(
        args.log_root, component="generation-worker", enable_console=False
    )
    batch_size = env_int(
        "TRAVEL_AGENT_GENERATION_WORKER_BATCH_SIZE", 1, minimum=1, maximum=100
    )
    poll_seconds = env_int(
        "TRAVEL_AGENT_GENERATION_WORKER_POLL_SECONDS", 2, minimum=1, maximum=60
    )
    if args.once:
        run_batch(worker, batch_size, logger)
        return
    run_loop(worker, batch_size, poll_seconds, logger)


def _worker_from_app(app: FastAPI) -> GenerationWorker:
    stale_after_seconds = env_int(
        "TRAVEL_AGENT_GENERATION_WORKER_STALE_AFTER_SECONDS",
        900,
        minimum=60,
        maximum=86400,
    )
    return GenerationWorker(
        cast(Callable[[], UnitOfWork], app.state.generation_uow_factory),
        cast(Clock, app.state.generation_clock),
        cast(GenerationHandler, app.state.generation_handler),
        stale_after_seconds=stale_after_seconds,
    )


if __name__ == "__main__":
    main()
