"""Emit the IFIP_SEC-X01_receipt_schema proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the IFIP_SEC-X01_receipt_schema task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "IFIP_SEC-X01_receipt_schema"

BASE_SHA = "e2f63ccb5522d4016d45bd6a9200adff971b4ae4"

CHANGED = [
    "research/venue2027/ifip_sec/protocols/receipt.schema.json",
    "research/venue2027/ifip_sec/tests/test_receipt_schema.py",
    "research/venue2027/proof/emit_IFIP_SEC-X01_receipt_schema_report.py",
    "research/venue2027/proof/IFIP_SEC-X01_receipt_schema.json",
    "research/venue2027/proof/logs/IFIP_SEC-X01_receipt_schema.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-X01_receipt_schema.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/ifip_sec/tests/test_receipt_schema.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X01_receipt_schema.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/ifip_sec/ --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-X01_receipt_schema.ruff.log",
    },
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=CHANGED[:2],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        notes=(
            "IFIP_SEC-X01_receipt_schema (Phase P02, RQ1): defined the canonical context-bound "
            "authorization receipt as JSON Schema draft 2020-12 (stdlib subset) at "
            "research/venue2027/ifip_sec/protocols/receipt.schema.json. All thirteen required "
            "fields canonicalized with additionalProperties:false: version (const '1', unknown "
            "versions fail closed with CONST_MISMATCH), tenant, principal, purpose (snake_case "
            "purpose-of-use), delegated_actor, operation (dotted governed-operation label), "
            "proposal_lineage_hash (lowercase 64-hex SHA-256, the X02 dispatch-digest binding "
            "incl. parent reference), policy_epoch, consent_epoch, nonce (>=16-char URL-safe "
            "consume-once token; atomic consumption remains X03's linearizable duty), issued_at/"
            "expiry (strict UTC RFC 3339) and signature{algorithm(HMAC-SHA256),value(64-hex)}. "
            "Fail closed throughout: no credential material, no health value - injected clinical "
            "fields are hard ADDITIONAL_PROPERTY rejections, tested explicitly. The stdlib 2020-"
            "12 subset cannot compare two instance fields, so 'expiry strictly after issued_at' "
            "is encoded as strict UTC timestamps in the schema and ENFORCED by the composed "
            "validator in the test driver with stable reason codes (TEMPORAL_ORDER for "
            "expiry<=issued_at, TIMESTAMP_UNPARSEABLE for indeterminate parses - never a silent "
            "pass). Test driver research/venue2027/ifip_sec/tests/test_receipt_schema.py (18 "
            "tests) imports ONLY the schema JSON and the shared stdlib validator (no candidate "
            "verifier - oracle independence preserved): 3+ positive receipts (canonical non-"
            "delegated with actor==principal, delegated multi-hop with distinct epochs and "
            "microsecond timestamps, boundary expiry one second after issuance, required-field "
            "completeness) and adversarial coverage (missing signature at both levels, expiry == "
            "issued_at, expiry < issued_at, four malformed proposal_lineage_hash variants, short "
            "signature value, unknown extra field, injected diagnosis text, missing nonce, "
            "unknown version, unknown signature algorithm, garbage timestamp, empty/wrong-type "
            "fields). 18 passed; uvx ruff@0.7.1 check clean on research/venue2027/ifip_sec/. "
            "No production path touched; no live provider, clock or randomness; no real "
            "PostgreSQL condition claimed (schema-only task). baseline_parity=NOT_APPLICABLE "
            "(structural contract, not a decision comparator; baseline arms B0-B4 are exercised "
            "by X05/X06). source_sha_after records the base commit e2f63ccb per the established "
            "sibling convention (IFIP_SEC-X06, POPETS-X06); the single task commit SHA is "
            "created immediately after this report and recorded in the commit body. Downstream "
            "consumers: IFIP_SEC-X02_lineage_digest, X03_nonce_store, X04_context_verify."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-X01_receipt_schema.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
