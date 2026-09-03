"""Bounded worker loop for recoverable holiday calendar synchronization jobs."""

from __future__ import annotations

from dataclasses import dataclass

from .holiday_calendar_sync import ChinaHolidayCalendarSyncService


@dataclass(frozen=True, slots=True)
class HolidayCalendarWorkerResult:
    processed_job_ids: tuple[str, ...]
    failed_job_id: str | None = None
    error_type: str | None = None


class HolidayCalendarSyncWorker:
    def __init__(self, service: ChinaHolidayCalendarSyncService) -> None:
        self._service = service

    def run_batch(self, *, max_jobs: int = 10) -> HolidayCalendarWorkerResult:
        if max_jobs < 1 or max_jobs > 100:
            raise ValueError("holiday calendar worker batch size must be between 1 and 100")
        processed: list[str] = []
        for _ in range(max_jobs):
            try:
                job = self._service.run_next()
            except Exception as exc:
                # The claimed job retains its running lease. A later worker
                # recovers it only after the lease expires, preventing a hot
                # failure loop and preserving the interrupted attempt.
                return HolidayCalendarWorkerResult(
                    tuple(processed), error_type=type(exc).__name__
                )
            if job is None:
                break
            processed.append(job.job_id)
        return HolidayCalendarWorkerResult(tuple(processed))
