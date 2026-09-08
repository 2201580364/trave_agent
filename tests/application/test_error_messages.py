"""Tests for the centralized error-message pipeline (api-contract.md §2.4).

Guarantees:
- every stable admin/planning code maps to complete Chinese user copy;
- details summaries only render whitelisted fields, never raw internals;
- the not-approvable error composes copy + readiness summary in message.
"""

from travel_agent.application.admin.errors import (
    PublicationGateRejectedError,
    ReviewRevisionNotApprovableError,
    SourceRecordInUseError,
)
from travel_agent.application.common.error_messages import (
    ADMIN_ERROR_MESSAGES,
    DEFAULT_ERROR_MESSAGE,
    PLANNING_ISSUE_MESSAGES,
    admin_error_message,
    summarize_error_details,
)
from travel_agent.application.common.errors import (
    DraftNotReadyError,
    InvalidAttractionReplacementError,
    InvalidStateTransitionError,
)


def _assert_chinese(text: str) -> None:
    assert any("\u4e00" <= char <= "\u9fff" for char in text), text


def test_every_registered_code_has_complete_chinese_copy() -> None:
    for code, message in ADMIN_ERROR_MESSAGES.items():
        assert message, code
        _assert_chinese(message)
        assert str(message).endswith("。"), code


def test_planning_issue_messages_are_chinese() -> None:
    for code, message in PLANNING_ISSUE_MESSAGES.items():
        _assert_chinese(message)
        assert message, code


def test_unknown_code_falls_back_to_safe_generic_copy() -> None:
    message = admin_error_message("totally_unknown_code")
    assert message == DEFAULT_ERROR_MESSAGE
    _assert_chinese(message)


def test_summary_ignores_unknown_details_fields() -> None:
    rendered = summarize_error_details(
        "review_revision_not_approvable",
        {"missing_checks": ["basic"], "sql_statement": "SELECT secret"},
    )
    assert "基础事实" in rendered
    assert "SELECT secret" not in rendered


def test_not_approvable_error_composes_copy_and_readiness_summary() -> None:
    error = ReviewRevisionNotApprovableError(missing_checks=("basic", "time"))
    assert "审核准备度未全部通过" in error.message
    assert "基础事实" in error.message
    assert "开放时间证据" in error.message
    assert error.details["missing_checks"] == ["basic", "time"]


def test_not_approvable_not_candidate_variant_mentions_resubmit() -> None:
    error = ReviewRevisionNotApprovableError(not_candidate=True)
    assert "重新送审" in error.message


def test_publication_gate_error_renders_reason_codes() -> None:
    error = PublicationGateRejectedError(("TIME_RULE_UNRESOLVED",))
    assert "发布门禁未通过" in error.message
    assert "TIME_RULE_UNRESOLVED" in error.message
    assert error.details["reason_codes"] == ("TIME_RULE_UNRESOLVED",)


def test_source_in_use_error_renders_references() -> None:
    error = SourceRecordInUseError(("source-1", "source-2"))
    assert "source-1" in error.message
    assert "source-2" in error.message


def test_draft_not_ready_error_translates_issue_codes() -> None:
    error = DraftNotReadyError(
        ("travel_facts_missing", "attraction_selection_empty")
    )
    assert "还未填写出行方式" in error.message
    assert "还未选择任何景点" in error.message
    assert error.details["issues"] == ("travel_facts_missing", "attraction_selection_empty")


def test_state_transition_errors_prefer_chinese_input_over_english() -> None:
    english = InvalidStateTransitionError("generation intent is no longer running")
    assert "当前状态不允许" in english.message
    chinese = InvalidStateTransitionError("当前状态的同步任务无法取消；正在执行的任务会自然完成")
    assert chinese.message == "当前状态的同步任务无法取消；正在执行的任务会自然完成"

    replacement = InvalidAttractionReplacementError(
        "replaced attraction is not part of the source draft"
    )
    assert "暂时无法替换该景点" in replacement.message
