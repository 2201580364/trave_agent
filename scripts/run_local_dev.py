"""Run the migrated SQLite + FastAPI local browser-validation backend."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> None:
    from travel_agent.runtime_config import load_runtime_environment

    load_runtime_environment(ROOT / ".env")
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--database",
        type=Path,
        default=None,
        help="SQLite file override; otherwise TRAVEL_AGENT_DATABASE_URL from .env is used",
    )
    args = parser.parse_args()

    if args.database is not None:
        database_path = args.database.resolve()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        database_url = f"sqlite:///{database_path.as_posix()}"
    else:
        database_url = os.environ.get(
            "TRAVEL_AGENT_DATABASE_URL",
            f"sqlite:///{(ROOT / '.local' / 'travel_agent.db').as_posix()}",
        )
        if database_url.startswith("sqlite:///"):
            configured_path = Path(database_url.removeprefix("sqlite:///"))
            database_path = (
                configured_path if configured_path.is_absolute() else ROOT / configured_path
            ).resolve()
            database_path.parent.mkdir(parents=True, exist_ok=True)
            database_url = f"sqlite:///{database_path.as_posix()}"
    os.environ["TRAVEL_AGENT_DATABASE_URL"] = database_url

    migration = Config(str(ROOT / "alembic.ini"))
    migration.set_main_option("script_location", str(ROOT / "migrations"))
    migration.set_main_option("prepend_sys_path", str(SRC))
    migration.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(migration, "head")

    from travel_agent.local_dev import app
    from travel_agent.observability import configure_file_logging

    configure_file_logging(ROOT / "logs", component="api", enable_console=False)

    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, access_log=False)


if __name__ == "__main__":
    main()
