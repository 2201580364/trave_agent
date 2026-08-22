"""File logging tests. Traceability: H3, ADR-0005."""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
from datetime import date
from pathlib import Path

from travel_agent.observability import configure_file_logging


def _read_json_lines(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _multiprocess_log_writer(log_root: str, worker_number: int, count: int) -> None:
    logger = configure_file_logging(
        Path(log_root),
        component="worker",
        logger_name=f"travel_agent.test.process.{os.getpid()}",
        date_provider=lambda: date(2026, 8, 22),
    )
    for index in range(count):
        logger.info(
            "concurrent message",
            extra={
                "event": "worker.concurrent",
                "request_id": f"{worker_number}-{index}",
            },
        )
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_logs_are_split_by_date_component_and_level(tmp_path: Path) -> None:
    logger = configure_file_logging(
        tmp_path,
        component="api",
        logger_name="travel_agent.test.logging",
        date_provider=lambda: date(2026, 8, 22),
    )

    logger.debug("debug message", extra={"event": "solver.debug"})
    logger.info(
        "solve completed",
        extra={"event": "solver.completed", "task_id": "task-1", "duration_ms": 12},
    )
    logger.warning("slow solve", extra={"event": "solver.slow"})
    logger.error("solve failed", extra={"event": "solver.failed", "error_code": "E1"})

    base = tmp_path / "api"
    debug_records = _read_json_lines(base / "debug" / "2026-08-22.log")
    info_records = _read_json_lines(base / "info" / "2026-08-22.log")
    error_records = _read_json_lines(base / "error" / "2026-08-22.log")

    assert [record["level"] for record in debug_records] == ["DEBUG"]
    assert [record["level"] for record in info_records] == ["INFO", "WARNING"]
    assert [record["level"] for record in error_records] == ["ERROR"]
    assert info_records[0]["event"] == "solver.completed"
    assert info_records[0]["task_id"] == "task-1"
    assert info_records[0]["duration_ms"] == 12
    assert error_records[0]["error_code"] == "E1"

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_daily_handler_switches_to_new_date_file(tmp_path: Path) -> None:
    current_date = [date(2026, 8, 22)]
    logger = configure_file_logging(
        tmp_path,
        component="worker",
        logger_name="travel_agent.test.rollover",
        date_provider=lambda: current_date[0],
    )

    logger.info("day one", extra={"event": "day.one"})
    current_date[0] = date(2026, 8, 23)
    logger.info("day two", extra={"event": "day.two"})

    info_dir = tmp_path / "worker" / "info"
    assert (info_dir / "2026-08-22.log").exists()
    assert (info_dir / "2026-08-23.log").exists()

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_logger_does_not_propagate_to_root_stdout_handlers(tmp_path: Path) -> None:
    logger = configure_file_logging(
        tmp_path,
        component="api",
        logger_name="travel_agent.test.no_propagation",
        date_provider=lambda: date(2026, 8, 22),
    )

    assert logger.propagate is False
    assert all(not isinstance(handler, logging.StreamHandler) for handler in logger.handlers)

    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)


def test_multiple_processes_write_complete_json_lines_to_one_module_file(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    processes = [
        context.Process(target=_multiprocess_log_writer, args=(str(tmp_path), worker, 25))
        for worker in range(2)
    ]

    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
        assert process.exitcode == 0

    records = _read_json_lines(tmp_path / "worker" / "info" / "2026-08-22.log")
    assert len(records) == 50
    assert len({record["request_id"] for record in records}) == 50
