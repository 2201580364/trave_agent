from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from travel_agent.infrastructure.database.place_catalog import (
    PlaceRevisionRow,
    PlaceRow,
    PlaceSourceRecordRow,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/import_candidate_revisions.py"


def _migrate(database: Path) -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.attributes["skip_dotenv"] = True
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database}")
    command.upgrade(config, "head")


def _run_import(database: Path, *, dry_run: bool = False) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT), "--database", str(database)]
    if dry_run:
        args.append("--dry-run")
    env = os.environ.copy()
    env.pop("TRAVEL_AGENT_DATABASE_URL", None)
    return subprocess.run(
        args,
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def _run_selected_import(
    database: Path, *, limit: int | None = None, candidate_ids: tuple[str, ...] = ()
) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT), "--database", str(database)]
    if limit is not None:
        args.extend(["--limit", str(limit)])
    for candidate_id in candidate_ids:
        args.extend(["--candidate-id", candidate_id])
    env = os.environ.copy()
    env.pop("TRAVEL_AGENT_DATABASE_URL", None)
    return subprocess.run(args, cwd=ROOT, env=env, check=True, capture_output=True, text=True)


def _counts(database: Path) -> tuple[int, int, int]:
    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        return (
            session.scalar(select(func.count()).select_from(PlaceRow)) or 0,
            session.scalar(select(func.count()).select_from(PlaceSourceRecordRow)) or 0,
            session.scalar(select(func.count()).select_from(PlaceRevisionRow)) or 0,
        )


def test_candidate_import_is_idempotent_and_keeps_revisions_candidate(tmp_path: Path) -> None:
    database = tmp_path / "candidate-import.db"
    _migrate(database)

    first = _run_import(database)
    assert "candidate revisions: imported=72, skipped=0, dry_run=False" in first.stdout
    assert _counts(database) == (72, 72, 72)

    engine = create_engine(f"sqlite:///{database}")
    with Session(engine) as session:
        statuses = set(session.scalars(select(PlaceRevisionRow.lifecycle_status)).all())
        eligible = session.scalar(
            select(func.count())
            .select_from(PlaceRevisionRow)
            .where(PlaceRevisionRow.solver_eligible.is_(True))
        )
    assert statuses == {"candidate"}
    assert eligible == 0

    second = _run_import(database)
    assert "candidate revisions: imported=0, skipped=72, dry_run=False" in second.stdout
    assert _counts(database) == (72, 72, 72)


def test_candidate_import_dry_run_does_not_write_rows(tmp_path: Path) -> None:
    database = tmp_path / "candidate-import-dry-run.db"
    _migrate(database)

    result = _run_import(database, dry_run=True)
    assert "candidate revisions: imported=72, skipped=0, dry_run=True" in result.stdout
    assert _counts(database) == (0, 0, 0)


def test_candidate_import_supports_controlled_batch_limit(tmp_path: Path) -> None:
    database = tmp_path / "candidate-import-small.db"
    _migrate(database)

    result = _run_selected_import(database, limit=12)

    assert "candidate revisions: imported=12, skipped=0, dry_run=False" in result.stdout
    assert _counts(database) == (12, 12, 12)


def test_candidate_import_supports_explicit_candidate_ids(tmp_path: Path) -> None:
    database = tmp_path / "candidate-import-ids.db"
    _migrate(database)

    result = _run_selected_import(database, candidate_ids=("hz-cand-008", "hz-cand-013"))

    assert "candidate revisions: imported=2, skipped=0, dry_run=False" in result.stdout
    assert _counts(database) == (2, 2, 2)
