"""Read-only readiness reporting for governed research Place revisions."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from travel_agent.application.admin.review import evaluate_review_readiness
from travel_agent.infrastructure.database.place_catalog import (
    SqlAlchemyPlaceCatalogRepository,
)
from travel_agent.infrastructure.database.place_review import (
    SqlAlchemyPlaceReviewRepository,
)

READINESS_CHECK_LABELS = {
    "basic": "基础信息",
    "source": "来源证据",
    "geometry": "地点几何",
    "access_point": "访问点",
    "time": "开放时间",
    "relation": "地点关系",
}


@dataclass(frozen=True, slots=True)
class ResearchReadinessItem:
    revision_id: str
    candidate_id: str
    canonical_name: str
    admin_area: str
    place_kind: str
    lifecycle_status: str
    solver_eligible: bool
    readiness_status: str
    completed_checks: int
    verified_checks: int
    total_checks: int
    missing_checks: tuple[str, ...]
    pending_review_checks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "revision_id": self.revision_id,
            "candidate_id": self.candidate_id,
            "canonical_name": self.canonical_name,
            "admin_area": self.admin_area,
            "place_kind": self.place_kind,
            "lifecycle_status": self.lifecycle_status,
            "solver_eligible": self.solver_eligible,
            "readiness_status": self.readiness_status,
            "completed_checks": self.completed_checks,
            "verified_checks": self.verified_checks,
            "total_checks": self.total_checks,
            "missing_checks": list(self.missing_checks),
            "pending_review_checks": list(self.pending_review_checks),
        }


@dataclass(frozen=True, slots=True)
class ResearchReadinessReport:
    database: str
    items: tuple[ResearchReadinessItem, ...]
    lifecycle_counts: dict[str, int]
    readiness_counts: dict[str, int]
    missing_check_counts: dict[str, int]
    pending_review_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "database": self.database,
            "total": len(self.items),
            "lifecycle_counts": self.lifecycle_counts,
            "readiness_counts": self.readiness_counts,
            "missing_check_counts": self.missing_check_counts,
            "pending_review_counts": self.pending_review_counts,
            "items": [item.to_dict() for item in self.items],
        }


def load_research_readiness(
    database: Path,
    *,
    candidate_ids: tuple[str, ...] = (),
    lifecycle_status: str | None = None,
) -> ResearchReadinessReport:
    """Evaluate selected Hangzhou candidates without changing workflow state."""

    path = database.resolve()
    if not path.is_file():
        raise ValueError(f"research database does not exist: {path}")
    requested = {_revision_id(value) for value in candidate_ids}
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with Session(engine) as session:
            reviews = SqlAlchemyPlaceReviewRepository(session)
            catalog = SqlAlchemyPlaceCatalogRepository(session)
            revisions = reviews.list_revisions(
                lifecycle_status=lifecycle_status,
                keyword=None,
                admin_area=None,
                place_kind=None,
                limit=1000,
                offset=0,
            )
            revisions = tuple(
                revision
                for revision in revisions
                if revision.place_revision_id.startswith("revision-hz-cand-")
                and (not requested or revision.place_revision_id in requested)
            )
            found = {revision.place_revision_id for revision in revisions}
            missing = requested - found
            if missing:
                raise ValueError(
                    "candidate revisions not found in selected lifecycle: "
                    + ", ".join(sorted(missing))
                )

            items: list[ResearchReadinessItem] = []
            for revision in sorted(revisions, key=lambda item: item.place_revision_id):
                evidence = catalog.load_revision_evidence(revision.place_revision_id)
                if evidence is None:
                    continue
                readiness = evaluate_review_readiness(
                    evidence,
                    reviews.get_open_task_for_revision(revision.place_revision_id),
                )
                items.append(
                    ResearchReadinessItem(
                        revision_id=revision.place_revision_id,
                        candidate_id=revision.place_revision_id.removeprefix("revision-"),
                        canonical_name=revision.canonical_name,
                        admin_area=revision.admin_area,
                        place_kind=revision.place_kind,
                        lifecycle_status=revision.lifecycle_status,
                        solver_eligible=revision.solver_eligible,
                        readiness_status=str(readiness["status"]),
                        completed_checks=_readiness_int(readiness, "completed_checks"),
                        verified_checks=_readiness_int(readiness, "verified_checks"),
                        total_checks=_readiness_int(readiness, "total_checks"),
                        missing_checks=_readiness_keys(readiness, "missing_checks"),
                        pending_review_checks=_readiness_keys(
                            readiness, "pending_review_checks"
                        ),
                    )
                )
    finally:
        engine.dispose()
    return summarize_research_readiness(path, tuple(items))


def summarize_research_readiness(
    database: Path, items: tuple[ResearchReadinessItem, ...]
) -> ResearchReadinessReport:
    lifecycle = Counter(item.lifecycle_status for item in items)
    readiness = Counter(item.readiness_status for item in items)
    missing = Counter(key for item in items for key in item.missing_checks)
    pending = Counter(key for item in items for key in item.pending_review_checks)
    return ResearchReadinessReport(
        database=str(database),
        items=items,
        lifecycle_counts=dict(sorted(lifecycle.items())),
        readiness_counts=dict(sorted(readiness.items())),
        missing_check_counts=dict(sorted(missing.items())),
        pending_review_counts=dict(sorted(pending.items())),
    )


def render_research_readiness_markdown(report: ResearchReadinessReport) -> str:
    lines = [
        "# 研究目录审核就绪报告",
        "",
        f"- 数据库：`{report.database}`",
        f"- 地点版本：{len(report.items)}",
        f"- 生命周期：{_render_counts(report.lifecycle_counts)}",
        f"- 准备状态：{_render_counts(report.readiness_counts)}",
        f"- 缺失项：{_render_check_counts(report.missing_check_counts)}",
        f"- 待审核项：{_render_check_counts(report.pending_review_counts)}",
        "",
        "| 候选 | 地点 | 类型 | 生命周期 | 已采集 | 已核验 | 缺失 | 待审核 |",
        "|---|---|---|---|---:|---:|---|---|",
    ]
    for item in report.items:
        lines.append(
            "| "
            + " | ".join(
                (
                    item.candidate_id,
                    item.canonical_name,
                    item.place_kind,
                    item.lifecycle_status,
                    f"{item.completed_checks}/{item.total_checks}",
                    f"{item.verified_checks}/{item.total_checks}",
                    _render_checks(item.missing_checks),
                    _render_checks(item.pending_review_checks),
                )
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _revision_id(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("revision-"):
        return normalized
    if normalized.startswith("hz-cand-"):
        return f"revision-{normalized}"
    raise ValueError(f"invalid Hangzhou candidate ID: {value}")


def _readiness_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise ValueError(f"review readiness {key} must be an integer")
    return value


def _readiness_keys(payload: dict[str, object], key: str) -> tuple[str, ...]:
    value = payload.get(key)
    if not isinstance(value, (tuple, list)) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"review readiness {key} must be a string sequence")
    return tuple(value)


def _render_counts(counts: dict[str, int]) -> str:
    return "、".join(f"{key} {value}" for key, value in counts.items()) or "无"


def _render_check_counts(counts: dict[str, int]) -> str:
    return "、".join(
        f"{READINESS_CHECK_LABELS.get(key, key)} {value}" for key, value in counts.items()
    ) or "无"


def _render_checks(checks: tuple[str, ...]) -> str:
    return "、".join(READINESS_CHECK_LABELS.get(key, key) for key in checks) or "无"
