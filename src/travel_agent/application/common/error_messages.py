"""Centralized user-facing error messages for admin error codes.

Single source of truth for stable Chinese user copy, keyed by the stable
machine codes defined in docs/specs/api-contract.md §15.4.  ApplicationError
message text must never be treated as a program contract; clients branch on
``code`` and use ``details`` for structured rendering.
"""

from __future__ import annotations

from collections.abc import Mapping

# Stable admin error code -> versioned user copy (Simplified Chinese).
ADMIN_ERROR_MESSAGES: Mapping[str, str] = {
    "admin_authentication_required": "管理员会话缺失、已失效或已撤销，请重新登录。",
    "admin_permission_denied": "当前管理员角色无权执行该操作，请联系安全管理员开通权限。",
    "admin_actor_version_conflict": "管理员资料已被其他操作更新，请刷新页面后重试。",
    "admin_operation_intent_conflict": "该管理操作标识已用于其他内容，请刷新页面后重新操作。",
    "admin_login_name_conflict": "该管理员登录名已存在，请使用其他登录名。",
    "admin_role_safety_violation": "该操作会破坏安全管理员恢复路径，已被拒绝。",
    "review_task_not_found": "审核任务不存在，可能已被删除或无权访问。",
    "review_task_conflict": "审核任务已被其他操作更新，请刷新页面后重试。",
    "review_revision_not_approvable": "审核准备度未全部通过，暂时无法审核通过。",
    "review_revision_not_candidate": "只有候选状态的修订版本可以送审，请刷新页面后确认当前状态。",
    "place_revision_version_conflict": "修订版本已被其他操作更新，请刷新页面后重试。",
    "source_record_in_use": "当前来源仍被地点证据引用，请先把这些证据改用其他来源。",
    "source_record_validation_failed": "来源记录未通过治理校验，请检查来源渠道、地址和采集方式。",
    "publication_gate_rejected": "发布门禁未通过，请先补齐依赖证据后再发布。",
    "projection_preparation_rejected": "求解投影暂不能准备，请先补齐所需证据。",
    "resource_not_found": "资源不存在或无权访问。",
    # Generic HTTP-level codes surfaced through the same structure.
    "domain_validation_failed": "提交内容未通过校验，请检查后重试。",
    "admin_network_error": "无法连接管理服务，请检查网络或服务状态。",
    "admin_request_failed": "管理请求失败，请稍后重试。",
    # User-facing (planning/sharing/feedback) codes; frontend renders `message`
    # directly, so these must always be complete Chinese copy.
    "draft_not_ready": "行程草稿还有未完成的条件，请先补齐后再生成。",
    "draft_version_conflict": "草稿已在其他页面更新，请恢复最新版本后继续。",
    "generation_intent_conflict": "该生成请求已被用于其他草稿内容，请刷新页面后重试。",
    "invalid_state_transition": "当前状态不允许执行该操作，请刷新页面后重试。",
    "trip_revision_conflict": "行程已生成更新版本，请先恢复最新版本后再调整。",
    "invalid_attraction_replacement": "暂时无法替换该景点，请刷新页面后重试。",
    "plan_share_intent_conflict": "该分享标识已用于其他行程内容，请重新创建分享。",
    "feedback_intent_conflict": "该反馈已提交过，请勿重复提交。",
    "resource_not_found_user": "内容不存在或已失效。",
}

# Fallback copy used when a code has no entry (never leak internals).
DEFAULT_ERROR_MESSAGE = "操作未完成，请稍后重试或联系管理员。"

# User-facing readiness issue codes produced by planning _readiness_issues.
PLANNING_ISSUE_MESSAGES: Mapping[str, str] = {
    "travel_facts_missing": "还未填写出行方式（到达/离开交通）",
    "arrival_transport_unconfirmed": "到达交通还未确认",
    "departure_transport_unconfirmed": "离开交通还未确认",
    "attraction_selection_empty": "还未选择任何景点",
}


def admin_error_message(code: str) -> str:
    """Return the stable user copy for a machine code."""
    return ADMIN_ERROR_MESSAGES.get(code, DEFAULT_ERROR_MESSAGE)


def summarize_error_details(code: str, details: Mapping[str, object] | None) -> str:
    """Append a human-readable summary of whitelisted details to the copy.

    Keep this aligned with the details whitelist in api-contract.md §2.4:
    only stable, structured fields are rendered; unknown fields are ignored
    so new details never leak raw internals into user-facing text.
    """
    if not details:
        return ""
    parts: list[str] = []

    missing = _string_list(details.get("missing_checks"))
    pending = _string_list(details.get("pending_review_checks"))
    if code == "review_revision_not_approvable" and (missing or pending):
        if missing:
            parts.append(
                "证据未采集齐：" + "；".join(_readiness_labels(item) for item in missing)
            )
        if pending:
            parts.append(
                "已采集但未逐条人工核验："
                + "；".join(_readiness_labels(item) for item in pending)
            )
    elif code == "review_revision_not_approvable" and details.get("not_candidate") is True:
        parts.append("当前修订版本已不是候选状态（可能已被编辑更新），请刷新页面后重新送审。")

    reason_codes = _string_list(details.get("reason_codes"))
    if reason_codes:
        parts.append("原因：" + "、".join(reason_codes))

    references = _string_list(details.get("references"))
    if references:
        parts.append("仍在使用：" + "、".join(references))

    issues = _string_list(details.get("issues"))
    if issues:
        parts.append("待处理：" + "；".join(_issue_labels(item) for item in issues))

    if not parts:
        return ""
    return "（" + "。".join(parts) + "。）"


_READINESS_CHECK_LABELS: Mapping[str, str] = {
    "basic": "基础事实（名称/分类/游览时长，需在详情页编辑并保存一次）",
    "source": "来源记录（需当前有效且冲突已裁决）",
    "geometry": "几何证据（O04 地图形状）",
    "access_point": "访问点证据（O04 进出端点）",
    "time": "开放时间证据（O05 周规则/闭馆日/日期例外）",
    "relation": "地点关系检查（O07 裁决与核验）",
}

_INTERNAL_DETAIL_KEYS = frozenset(
    {
        "expected_version",
        "current_version",
        "required_permission",
        "not_candidate",
        "missing_checks",
        "pending_review_checks",
        "reason_codes",
        "references",
        "issues",
    }
)


def _readiness_labels(key: str) -> str:
    return _READINESS_CHECK_LABELS.get(key, key)


def _issue_labels(key: str) -> str:
    return PLANNING_ISSUE_MESSAGES.get(key, key)


def _string_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if isinstance(item, str)]
    return []
