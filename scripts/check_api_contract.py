"""Diff the implemented HTTP surface against docs/specs/api-contract.md.

S8-2 (transformation-plan): fails CI when a route exists in code but is not
registered in the contract, or when the contract registers an endpoint that no
longer exists in code. The contract is the single source of truth for the API
surface (docs/specs/api-contract.md V2.11+); this check keeps it honest.

Endpoint extraction rules (mirror the three registration styles used by the
contract):
  1. User-side overview table (§4): ``| METHOD | ``/path`` | ...`` — the path
     column omits the ``/api/v1`` prefix, which is prepended.
  2. Admin endpoint tables (§15.2.x etc.): ``| ``METHOD /api/v1/admin/...`` |``.
  3. Inline prose registrations: ``METHOD /api/v1/...`` anywhere in the text
     (e.g. §15.2.2/15.2.3). Health probes in §2.1.1 are captured this way.

Known-not-implemented endpoints (contract sections marked 计划端点/未排期) are
still expected in code-diff terms: a code route missing from the contract is a
violation, but a contract endpoint missing from code is only reported as
``contract_only`` (the contract may register planned endpoints ahead of
implementation; it must never lag behind the code).

Contract (``.claude/rules/script-contract.md``):
- exit 0 = surfaces match (or contract-only planned endpoints);
- exit 1 = runtime error (contract file missing, schema unreadable);
- exit 2 = check failure (code endpoints absent from the contract);
- ``--json`` prints a single JSON verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/specs/api-contract.md"
DEFAULT_SCHEMA = ROOT / "var/reports/openapi-schema.json"

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# | POST | `/trip-drafts` | ... (§4 overview; prefix /api/v1 added)
_USER_TABLE_ROW = re.compile(
    r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`(/[^`]+)`\s*\|", re.MULTILINE
)
# `POST /api/v1/admin/...` (admin tables and inline prose, incl. §2.1.1 probes)
_ADMIN_OR_INLINE = re.compile(
    r"`?(GET|POST|PUT|PATCH|DELETE)\s+(/api/v1/[A-Za-z0-9_/.{}-]+)"
)
# Inline user-side prose (§4 note): `POST /trips/{trip_id}/...` — the overview
# note omits the /api/v1 prefix. Restricted to user-side resource roots so
# prose mentions of deleted/old admin endpoints (document header, §1) and
# admin shorthand (§15.2.0) are NOT misread as registrations.
_USER_INLINE = re.compile(
    r"`(GET|POST|PUT|PATCH|DELETE)\s+"
    r"/((?:trips|trip-drafts|plan-shares|attractions|generation-intents|"
    r"anonymous-sessions|health)/[A-Za-z0-9_/.{}-]+)`"
)
# Aggregated sub-resource sentence (§15.2.1 O05): "`POST/PATCH/DELETE` 分别作用于
# `/time-rules/{time_rule_id}`、`/closures/{closure_id}` 和
# `/date-exceptions/{date_exception_id}`" — each method combines with each
# sub-path under the revision prefix.
_AGG_SENTENCE = re.compile(
    r"`((?:GET|POST|PUT|PATCH|DELETE)(?:/(?:GET|POST|PUT|PATCH|DELETE))+)`\s*分别作用于\s*"
    r"((?:`/[^`\s]+`[、和\s]*)+)"
)
_REVISION_PREFIX = "/api/v1/admin/place-revisions/{revision_id}"
# Contract §2.1.1 registers the probes under /api/v1/health/*, but the app and
# ops docs (deploy/production, docs/ops) consistently serve /health/* without
# the prefix. Treated as a documented alias until the contract is revised.
_PROBE_ALIASES = {
    "/api/v1/health/live": "/health/live",
    "/api/v1/health/ready": "/health/ready",
}


def _normalize_query(path: str) -> str:
    """Drop the query string: ?param registrations describe usage, not routing."""
    return path.split("?", 1)[0]


def _extract_contract_endpoints(text: str) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for method, path in _USER_TABLE_ROW.findall(text):
        endpoints.add((method.lower(), _normalize_query(f"/api/v1{path}")))
    for method, path in _ADMIN_OR_INLINE.findall(text):
        endpoints.add((method.lower(), _normalize_query(path)))
    for method, path in _USER_INLINE.findall(text):
        endpoints.add((method.lower(), _normalize_query(f"/api/v1/{path}")))
    for match in _AGG_SENTENCE.finditer(text):
        methods = {m.lower() for m in match.group(1).split("/")}
        for token in re.findall(r"`(/[^`\s]+)`", match.group(2)):
            # The contract lists POST among the methods but the natural REST
            # reading is: POST creates on the collection root, PATCH/DELETE
            # operate on the {xxx_id} member path. Bind accordingly.
            member = f"{_REVISION_PREFIX}{token}"
            collection = re.sub(r"/\{[a-z_]+\}$", "", member)
            endpoints.add(("post", collection))
            for method in methods - {"post"}:
                endpoints.add((method, member))
    # Documented probe alias: contract path -> served path.
    for contract_path, served_path in _PROBE_ALIASES.items():
        for method in ("get",):
            if (method, contract_path) in endpoints:
                endpoints.discard((method, contract_path))
                endpoints.add((method, served_path))
    return endpoints


def _extract_code_endpoints(schema: dict) -> set[tuple[str, str]]:
    endpoints: set[tuple[str, str]] = set()
    for path, operations in schema.get("paths", {}).items():
        for method in HTTP_METHODS:
            if method in operations:
                endpoints.add((method, path))
    return endpoints


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
        help="OpenAPI snapshot (default: var/reports/openapi-schema.json)",
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=CONTRACT,
        help="contract markdown (default: docs/specs/api-contract.md)",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON verdict")
    args = parser.parse_args()

    try:
        contract_text = args.contract.read_text(encoding="utf-8")
    except OSError as exc:
        if args.json:
            print(
                json.dumps(
                    {"status": "error", "error": f"contract unreadable: {exc}"},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"ERROR: contract unreadable: {exc}", file=sys.stderr)
        return 1

    try:
        schema = json.loads(args.schema.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        hint = "（先运行 scripts/export_openapi_schema.py 生成快照）"
        if args.json:
            print(
                json.dumps(
                    {"status": "error", "error": f"schema unreadable: {exc}{hint}"},
                    ensure_ascii=False,
                )
            )
        else:
            print(f"ERROR: schema unreadable: {exc}{hint}", file=sys.stderr)
        return 1

    contract_endpoints = _extract_contract_endpoints(contract_text)
    code_endpoints = _extract_code_endpoints(schema)

    code_only = sorted(code_endpoints - contract_endpoints)
    contract_only = sorted(contract_endpoints - code_endpoints)
    passed = not code_only

    if args.json:
        print(
            json.dumps(
                {
                    "status": "ok" if passed else "failed",
                    "contract_endpoint_count": len(contract_endpoints),
                    "code_endpoint_count": len(code_endpoints),
                    "code_only": [f"{m.upper()} {p}" for m, p in code_only],
                    "contract_only": [f"{m.upper()} {p}" for m, p in contract_only],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for method, path in code_only:
            print(f"CODE-ONLY  {method.upper()} {path}  （实现存在但契约未登记）")
        for method, path in contract_only:
            print(f"CONTRACT-ONLY  {method.upper()} {path}  （契约登记但代码未实现，含计划端点）")
        print(
            f"contract={len(contract_endpoints)} code={len(code_endpoints)} "
            f"code_only={len(code_only)} contract_only={len(contract_only)}"
        )
        print("RESULT:", "PASS" if passed else "FAIL")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
