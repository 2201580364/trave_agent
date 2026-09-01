"""Create an empty, migrated SQLite database for test or research data."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from travel_agent.data_governance.isolated_database import (  # noqa: E402
    DatabaseEnvironment,
    IsolatedDatabaseError,
    validate_isolated_database_target,
)


def initialize_database(database: Path, *, environment: str) -> DatabaseEnvironment:
    if environment not in {"test", "research"}:
        raise IsolatedDatabaseError("environment must be test or research")
    target = validate_isolated_database_target(
        database, local_database=ROOT / ".local" / "travel_agent.db"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    database_url = f"sqlite:///{target.as_posix()}"
    migration = Config(str(ROOT / "alembic.ini"))
    migration.attributes["skip_dotenv"] = True
    migration.set_main_option("script_location", str(ROOT / "migrations"))
    migration.set_main_option("prepend_sys_path", str(SRC))
    migration.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(migration, "head")

    marker = target.with_suffix(target.suffix + ".environment.json")
    marker.write_text(
        json.dumps(
            {
                "environment": environment,
                "database": str(target),
                "schema": "head",
                "created_at": datetime.now(UTC).isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return DatabaseEnvironment(environment, target)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=("test", "research"), required=True)
    parser.add_argument("--database", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = initialize_database(args.database, environment=args.environment)
    except IsolatedDatabaseError as exc:
        print(f"isolated database initialization refused: {exc}", file=sys.stderr)
        return 2
    print(f"initialized {result.name} database: {result.database}")
    print(f"environment marker: {result.database}.environment.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
