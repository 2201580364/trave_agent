"""Process loop for an injected durable generation worker (H3/S8)."""

from __future__ import annotations

import logging
import os
import signal
import threading

from travel_agent.application.planning.worker import GenerationWorker


def run_loop(
    worker: GenerationWorker, batch_size: int, poll_seconds: int, logger: logging.Logger
) -> None:
    stop = threading.Event()

    def request_stop(signum: int, frame: object) -> None:
        del frame
        logger.info(
            "generation worker stop requested",
            extra={"event": "stop", "error_code": str(signum)},
        )
        stop.set()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)
    logger.info("generation worker started", extra={"event": "started"})
    while not stop.is_set():
        run_batch(worker, batch_size, logger)
        stop.wait(poll_seconds)
    logger.info("generation worker stopped", extra={"event": "stopped"})


def run_batch(worker: GenerationWorker, batch_size: int, logger: logging.Logger) -> None:
    result = worker.run_batch(max_jobs=batch_size)
    if result.recovered_count or result.processed_intent_ids:
        logger.info(
            "generation worker batch completed",
            extra={"event": "batch", "task_id": ",".join(result.processed_intent_ids)},
        )
    if result.error_type:
        logger.error(
            "generation worker batch interrupted",
            extra={
                "event": "batch_error",
                "task_id": result.failed_intent_id,
                "error_code": result.error_type,
            },
        )


def env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
    return value
