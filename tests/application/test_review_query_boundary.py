"""H3/S7-1: query requests never change persisted review state."""

import pytest
from sqlalchemy import select

from tests.application.test_admin_identity_http import (
    ROOT_LOGIN,
    ROOT_PASSWORD,
    AdminTestContext,
    _login,
    _seed_approvable_candidate,
)
from tests.application.test_admin_identity_http import admin_context as admin_context
from travel_agent.infrastructure.database.admin_identity import AdminAuditEventRow
from travel_agent.infrastructure.database.place_catalog import PlaceRevisionRow


@pytest.mark.parametrize(
    "suffix",
    [
        "candidates",
        "dashboard-summary",
        "place-revisions/revision-query",
        "place-revisions/revision-query/evidence",
    ],
)
def test_queries_preserve_state(admin_context: AdminTestContext, suffix: str) -> None:
    context = admin_context
    _seed_approvable_candidate(context, "revision-query")
    _, headers = _login(context.client, ROOT_LOGIN, ROOT_PASSWORD)

    def state():
        with context.sessions() as session:
            return [
                [dict(row) for row in session.execute(select(model.__table__)).mappings()]
                for model in (PlaceRevisionRow, AdminAuditEventRow)
            ]

    before = state()
    for _ in range(2):
        result = context.client.get("/api/v1/admin/" + suffix, headers=headers)
        assert result.status_code == 200, result.text
        assert state() == before
