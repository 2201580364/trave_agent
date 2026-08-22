"""Monthly log archive tests. Traceability: H3, ADR-0005."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest

from travel_agent.observability import archive_completed_months


def _daily_log(root: Path, component: str, level: str, day: str, content: str) -> Path:
    path = root / component / level / f"{day}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_completed_months_are_archived_and_current_month_is_kept(tmp_path: Path) -> None:
    august_debug = _daily_log(tmp_path, "api", "debug", "2026-08-22", "debug")
    august_info = _daily_log(tmp_path, "api", "info", "2026-08-23", "info")
    september_info = _daily_log(tmp_path, "api", "info", "2026-09-01", "current")

    archives = archive_completed_months(tmp_path, today=date(2026, 9, 2))

    assert len(archives) == 2
    assert not august_debug.exists()
    assert not august_info.exists()
    assert september_info.exists()

    debug_archive = tmp_path / "archive" / "2026-08" / "api-debug.zip"
    info_archive = tmp_path / "archive" / "2026-08" / "api-info.zip"
    with ZipFile(debug_archive) as archive:
        assert archive.namelist() == ["api/debug/2026-08-22.log"]
        assert archive.read(archive.namelist()[0]).decode() == "debug"
    with ZipFile(info_archive) as archive:
        assert archive.namelist() == ["api/info/2026-08-23.log"]


def test_archive_is_idempotent_when_no_source_files_remain(tmp_path: Path) -> None:
    _daily_log(tmp_path, "worker", "error", "2026-07-31", "error")

    first = archive_completed_months(tmp_path, today=date(2026, 8, 1))
    second = archive_completed_months(tmp_path, today=date(2026, 8, 1))

    assert len(first) == 1
    assert second == ()


def test_corrupt_existing_archive_does_not_delete_source_log(tmp_path: Path) -> None:
    source = _daily_log(tmp_path, "api", "info", "2026-08-22", "must survive")
    archive_path = tmp_path / "archive" / "2026-08" / "api-info.zip"
    archive_path.parent.mkdir(parents=True)
    archive_path.write_bytes(b"not a zip")

    with pytest.raises(BadZipFile):
        archive_completed_months(tmp_path, today=date(2026, 9, 1))

    assert source.exists()
    assert source.read_text(encoding="utf-8") == "must survive"
