"""Export the FastAPI OpenAPI schema offline (no server, no MySQL).

S8-2 (transformation-plan): CI-friendly snapshot of the live HTTP surface so
that ``check_api_contract.py`` can diff the implemented routes against the
registered endpoints in docs/specs/api-contract.md.

The app is assembled exactly like the production composition root
(``interfaces/http/composition.py``) but fully offline: in-memory SQLite, real
database-backed services, governance catalog loaded from ``data/governance/``,
and holiday-sync workers set to ``None`` (unconfigured — same as an environment
without O17 settings). All admin router blocks must be mounted so the snapshot
covers the full contract surface; bootstrap is NOT called (the snapshot must be
side-effect free).

Contract (``.claude/rules/script-contract.md``):
- exit 0 = export written; exit 1 = runtime error;
- ``--json`` prints a single JSON verdict to stdout;
- default output is ``var/reports/openapi-schema.json`` (var/ is gitignored).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_OUTPUT = ROOT / "var/reports/openapi-schema.json"


def _build_schema() -> dict:
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from travel_agent.application.admin import (
        AdminIdentityService,
        GovernedSourceCatalog,
        PlaceReviewWorkflowService,
    )
    from travel_agent.application.admin.holiday_calendar_sync import (
        ChinaHolidayCalendarSyncService,
    )
    from travel_agent.infrastructure.database import (
        AnonymousIdentityService,
        SqlAlchemyAdminUnitOfWork,
        SqlAlchemyHolidayCalendarUnitOfWork,
        SqlAlchemyPublishedHolidayCalendarCatalog,
    )
    from travel_agent.infrastructure.database.planning import (
        SqlAlchemyUnitOfWork,
        create_schema,
    )
    from travel_agent.infrastructure.ids import UuidIdGenerator
    from travel_agent.infrastructure.memory import SystemClock
    from travel_agent.interfaces.http.app import HttpContainer, create_app

    governance_dir = ROOT / "data/governance"
    engine = create_engine("sqlite://")
    create_schema(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    clock = SystemClock()
    ids = UuidIdGenerator()
    identity = AnonymousIdentityService(sessions, clock, ids)
    admin_identity = AdminIdentityService(
        lambda: SqlAlchemyAdminUnitOfWork(sessions), clock, ids
    )
    review_workflow = PlaceReviewWorkflowService(
        lambda: SqlAlchemyAdminUnitOfWork(sessions),
        clock,
        ids,
        GovernedSourceCatalog.from_files(
            governance_dir / "hangzhou-source-registry-v1.json",
            governance_dir / "place-collection-field-dictionary-v1.json",
        ),
        SqlAlchemyPublishedHolidayCalendarCatalog(sessions),
    )
    # O17 workers unconfigured (None) mirrors a production env without holiday
    # sync settings; the sync router block still mounts on the service itself.
    holiday_calendar_sync = ChinaHolidayCalendarSyncService(
        lambda: SqlAlchemyHolidayCalendarUnitOfWork(sessions),
        clock,
        ids,
        discoverer=None,
        fetcher=None,
        extractor=None,
        worker_available=False,
        job_submission_available=False,
    )
    container = HttpContainer(
        lambda: SqlAlchemyUnitOfWork(sessions),
        clock,
        ids,
        None,  # snapshots: only used by generation endpoints' responses
        None,  # executor: never invoked by schema generation
        identity,
        admin_identity=admin_identity,
        review_workflow=review_workflow,
        holiday_calendar_sync=holiday_calendar_sync,
    )
    app = create_app(container)
    schema = app.openapi()
    schema["x-exported-at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return schema


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="output path (default: var/reports/openapi-schema.json)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON verdict")
    args = parser.parse_args()

    try:
        schema = _build_schema()
        path_count = len(schema.get("paths", {}))
        payload = json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        display = args.output.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        display = str(args.output)

    if args.json:
        print(
            json.dumps(
                {
                    "status": "ok",
                    "output": display,
                    "path_count": path_count,
                },
                ensure_ascii=False,
            )
        )
    else:
        print(f"Exported {path_count} paths -> {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
