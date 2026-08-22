"""Safe monthly ZIP archival for completed daily log files.

Traceability: H3, ADR-0005 D2.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from .file_lock import InterProcessFileLock

DAILY_LOG_PATTERN = re.compile(r"^(?P<day>\d{4}-\d{2}-\d{2})\.log$")


def archive_completed_months(log_root: Path, *, today: date | None = None) -> tuple[Path, ...]:
    """Archive daily logs from months earlier than ``today``.

    The expected source layout is ``<root>/<component>/<level>/<date>.log``.
    Sources are deleted only after the temporary archive passes integrity and
    membership checks and atomically replaces the destination archive.
    """

    current_day = today or date.today()
    current_month = current_day.strftime("%Y-%m")
    grouped: dict[tuple[Path, str], list[Path]] = defaultdict(list)

    if not log_root.exists():
        return ()

    for path in log_root.glob("*/*/*.log"):
        match = DAILY_LOG_PATTERN.match(path.name)
        if match is None:
            continue
        month = match.group("day")[:7]
        if month < current_month:
            grouped[(path.parent, month)].append(path)

    archives: list[Path] = []
    for (source_dir, month), sources in sorted(
        grouped.items(),
        key=lambda item: (str(item[0][0]), item[0][1]),
    ):
        archive = _archive_group(log_root, source_dir, month, sorted(sources))
        if archive is not None:
            archives.append(archive)
    return tuple(archives)


def _archive_group(
    log_root: Path,
    source_dir: Path,
    month: str,
    sources: Sequence[Path],
) -> Path | None:
    component = source_dir.parent.name
    level = source_dir.name
    archive_dir = log_root / "archive" / month
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / f"{component}-{level}.zip"
    temporary = destination.with_suffix(".zip.tmp")

    try:
        with InterProcessFileLock(source_dir / ".write.lock"):
            existing_sources = [source for source in sources if source.exists()]
            if not existing_sources:
                return None
            expected_names = {
                f"{component}/{level}/{source.name}"
                for source in existing_sources
            }
            with ZipFile(temporary, mode="w", compression=ZIP_DEFLATED) as output:
                existing_names: set[str] = set()
                if destination.exists():
                    with ZipFile(destination, mode="r") as existing:
                        bad_member = existing.testzip()
                        if bad_member is not None:
                            raise BadZipFile(f"corrupt member in existing archive: {bad_member}")
                        for member in existing.infolist():
                            output.writestr(member, existing.read(member.filename))
                            existing_names.add(member.filename)

                for source in existing_sources:
                    archive_name = f"{component}/{level}/{source.name}"
                    if archive_name not in existing_names:
                        output.write(source, arcname=archive_name)

            with ZipFile(temporary, mode="r") as verification:
                bad_member = verification.testzip()
                if bad_member is not None:
                    raise BadZipFile(f"corrupt member in temporary archive: {bad_member}")
                if not expected_names.issubset(verification.namelist()):
                    raise BadZipFile("temporary archive is missing expected log files")

            temporary.replace(destination)
            for source in existing_sources:
                source.unlink()
            return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive completed travel-agent log months")
    parser.add_argument("log_root", type=Path, nargs="?", default=Path("logs"))
    args = parser.parse_args()
    for archive in archive_completed_months(args.log_root):
        print(archive)


if __name__ == "__main__":
    main()
