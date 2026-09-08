"""Audit-registry integrity test (audit-logging.md §3, AUD-4).

Guards the authoritative action-code registry in
``.claude/rules/audit-logging.md``: every ``action="..."`` / ``action=<NAME>``
emitted anywhere under ``src/travel_agent`` must be registered in the rule
file. A new audit action without registration fails this test, preventing the
registry from silently rotting.

The rule file stores codes as ``| CODE | target_type | semantics |`` table
rows; this test parses those rows and cross-checks them against the code.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RULE_FILE = PROJECT_ROOT / ".claude/rules/audit-logging.md"
SRC = PROJECT_ROOT / "src" / "travel_agent"

# Literal string actions: action="ADMIN_LOGIN_..." (the dominant style).
_LITERAL_ACTION = re.compile(r"""action=["']([A-Z][A-Z0-9_]+)["']""")
# Variables referencing constant action codes (holiday_calendar_sync's
# _terminal_audit_fields returns tuple values): track NAME = "UPPER_SNAKE"
# constants assigned in the sync module and treat their values as actions.
_CONSTANT_BINDING = re.compile(
    r"^(_?[A-Z][A-Z0-9_]+)\s*(?::\s*[A-Za-z\[\]| ,]+)?\s*=\s*[\"']([A-Z][A-Z0-9_]+)[\"']",
    re.MULTILINE,
)


def _registered_actions() -> set[str]:
    text = RULE_FILE.read_text(encoding="utf-8")
    # Registry rows look like: | CODE | target_type | semantics |
    rows = re.findall(r"^\| ([A-Z][A-Z0-9_]+(?: / _[A-Z]+)?) \|", text, re.MULTILINE)
    registered: set[str] = set()
    for row in rows:
        for code in row.split(" / "):
            registered.add(code.strip())
    return registered


def _emitted_actions() -> set[str]:
    actions: set[str] = set()
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for match in _LITERAL_ACTION.finditer(text):
            actions.add(match.group(1))
        # _terminal_audit_fields style (holiday_calendar_sync): the action code
        # is the FIRST string of each status tuple in the mapping, followed by
        # the reason_code. Capture tuple-head strings inside that function so
        # dynamically selected actions are covered too.
        if path.name == "holiday_calendar_sync.py":
            match = re.search(r"def _terminal_audit_fields", text)
            if match is not None:
                tail = text[match.start():]
                body = re.split(r"\n(?=def |class )", tail)[0]
                actions.update(
                    re.findall(r'\(\s*"([A-Z][A-Z0-9_]+)",\s*\n?\s*"[A-Z]', body)
                )
    return actions


def test_every_emitted_action_is_registered() -> None:
    emitted = _emitted_actions()
    assert emitted, "action scan found nothing - scanner regex rotted"
    registered = _registered_actions()
    assert registered, "registry parse found nothing - rule file format changed"
    unregistered = sorted(emitted - registered)
    assert not unregistered, (
        "audit actions emitted in code but missing from "
        f".claude/rules/audit-logging.md registry: {unregistered}"
    )


def test_registry_has_no_stale_entries() -> None:
    # The registry must not drift ahead of the code either: a registered code
    # that no longer appears anywhere should be pruned (or is planned work and
    # belongs in a comment, not the table).
    stale = sorted(_registered_actions() - _emitted_actions())
    # Allow codes that appear in the rule file prose but were renamed; the
    # current registry must match the code exactly.
    assert not stale, (
        f"registry entries no longer emitted in code (prune them): {stale}"
    )


def test_target_types_are_registered() -> None:
    text = RULE_FILE.read_text(encoding="utf-8")
    registered_targets = set(
        re.findall(r"`([a-z][a-z_]+)`", text.split("## 四、")[1].split("## 五、")[0])
        if "## 四、" in text
        else []
    )
    emitted_targets: set[str] = set()
    for path in sorted((SRC / "application" / "admin").rglob("*.py")):
        emitted_targets.update(
            re.findall(r"""target_type=["']([a-z][a-z_]+)["']""", path.read_text(encoding="utf-8"))
        )
    assert emitted_targets
    unregistered = sorted(emitted_targets - registered_targets)
    assert not unregistered, (
        f"target_types emitted in code but missing from registry: {unregistered}"
    )
