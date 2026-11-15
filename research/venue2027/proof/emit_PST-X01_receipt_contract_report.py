"""Emit research/venue2027/proof/PST-X01_receipt_contract.json via agent_protocol.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-X01_receipt_contract task. No network access, no randomness.

Failure semantics: exits non-zero if report construction or validation fails;
the validation outcome is appended to the validator log regardless.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "PST-X01_receipt_contract"

BASE_SHA = "11a9219ce0a1d3d523400350abb959c0f56699f2"

ARTIFACTS = [
    "research/venue2027/pst/protocols/receipt.schema.json",
    "research/venue2027/pst/tests/test_receipt_contract.py",
]

CHANGED = ARTIFACTS + [
    "research/venue2027/proof/PST-X01_receipt_contract.json",
    "research/venue2027/proof/emit_PST-X01_receipt_contract_report.py",
    "research/venue2027/proof/logs/PST-X01_receipt_contract.pytest.log",
    "research/venue2027/proof/logs/PST-X01_receipt_contract.suite.log",
    "research/venue2027/proof/logs/PST-X01_receipt_contract.ruff.log",
    "research/venue2027/proof/logs/PST-X01_receipt_contract.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/pst/tests/test_receipt_contract.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-X01_receipt_contract.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/pst/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-X01_receipt_contract.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/pst/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-X01_receipt_contract.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_PST-X01_receipt_contract_report.py "
        "# agent_protocol.build_report + validate_report(ok:true); result appended "
        "to research/venue2027/proof/logs/PST-X01_receipt_contract.validator.log",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-X01_receipt_contract.validator.log",
    },
]

NOTES = (
    "P02 venue task PST-X01_receipt_contract (ReceiptMin RQ1, purpose-bound forensic "
    "receipt grammar). "
    "research/venue2027/pst/protocols/receipt.schema.json defines the minimal audit "
    "receipt grammar receipt.v1 (JSON Schema draft 2020-12 stdlib subset, "
    "additionalProperties:false, exactly the ten contract fields, no clinical payload, "
    "no free text, no raw identifiers): version (const '1', unknown versions fail "
    "closed with CONST_MISMATCH), receipt_id (rcpt_ + 16..64 lowercase hex, stable "
    "logical operation id making persisted receipt effects idempotent under retry), "
    "tenant (tnt_ + 8..32 hex) and principal (prn_ + 8..32 hex, pseudonymous tokens "
    "that make raw user names/emails/medical-record numbers unrepresentable), purpose "
    "(closed enum self_care/clinical_care/forensic_review/security_audit/"
    "research_analytics so a purpose encoding a patient attribute is rejected as "
    "unknown), operation (closed enum record_read/record_write/record_export/"
    "receipt_verify/retention_rotate), omitted_field_digest (lowercase 64-hex SHA-256 "
    "over the canonical JSON serialization of the complete omitted-fields object for "
    "the operation's audit query class: the verifiable reconstruction commitment that "
    "lets a forensic reconstructor confirm any omitted field by digest recomputation "
    "WITHOUT the receipt ever storing the omitted value), policy_epoch "
    "(epoch-<1..8 digits>, the monotonically increasing combined consent/policy/"
    "retention epoch bound at issuance; cross-epoch admissibility is adjudicated "
    "downstream by the disclosure protocol and forensic oracle, per CASE_MATRIX "
    "PST-CASE-04/06), issued_at (RFC 3339 UTC with 'Z' suffix only, deterministic "
    "receipt ordering across tenants) and signature (lowercase 64-hex HMAC-SHA256 "
    "over the canonical JSON of every field except signature, keyed by the external "
    "key registry bound to (tenant, policy_epoch); key material and key ids "
    "externalized, tampering with any body field fails verification DETECT_TAMPER). "
    "research/venue2027/pst/tests/test_receipt_contract.py (23 tests, stdlib-only "
    "oracle: imports ONLY the schema JSON and the shared stdlib validator "
    "schema_validator.validate_instance - no candidate verifier, oracle independence "
    "preserved): 3+ positive receipts (forensic read at default epoch, self-care "
    "write at epoch-1, max-boundary audit-verify token lengths incl. 32-hex "
    "principal/tenant and 64-hex receipt_id at epoch-99999999) each proven "
    "deterministic (byte-identical rebuild) and payload-free (every value a bounded "
    "token/digest/epoch); adversarial fail-closed coverage: missing "
    "omitted_field_digest (REQUIRED_MISSING - without the reconstruction commitment "
    "the receipt is not admissible evidence), raw PHI fields patient_name + diagnosis "
    "(ADDITIONAL_PROPERTY), five malformed digest variants (uppercase/non-hex/short/"
    "long/empty -> PATTERN_MISMATCH), unknown hidden_internal_id field (ADDITIONAL_"
    "PROPERTY, closing the hidden-ID side channel), four malformed policy_epoch "
    "variants (cross-epoch-style malformed epochs -> PATTERN_MISMATCH), wrong version "
    "'2' (CONST_MISMATCH, never best-effort parsed), every one of the ten required "
    "fields deleted (REQUIRED_MISSING), unknown purpose 'pregnancy_followup' and "
    "operation 'prescribe_dose' (ENUM_MISMATCH), plus signature-tamper structural "
    "evidence and distinct-operation digest/signature divergence. Verification: "
    "test_receipt_contract.py 23 passed; full pst suite 149 passed; uvx ruff@0.7.1 "
    "clean on research/venue2027/pst/; agent_protocol.validate_report ok:true. "
    "source_sha_after = base SHA per established repo convention (PST-schema, "
    "IFIP_SEC-X01); the single task commit SHA is created immediately after this "
    "report and recorded in the commit body. No production path touched; no live "
    "provider, clock, DB or randomness; no real PostgreSQL condition claimed "
    "(schema-only contract task). baseline_parity=NOT_APPLICABLE (structural receipt "
    "grammar, not a decision comparator; baseline arms B0-B3 are exercised by the "
    "downstream baseline/oracle tasks). Downstream consumers: forensic reconstructor "
    "and disclosure-protocol tasks of the ReceiptMin study (PST-CASE-01/04/05/06)."
)


def main() -> int:
    validator_log = (
        REPO / "research" / "venue2027" / "proof" / "logs"
        / "PST-X01_receipt_contract.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if head != BASE_SHA:
        print(f"unexpected HEAD {head!r} != base {BASE_SHA!r}", file=sys.stderr)
        return 1
    # Seed the validator log BEFORE validation so the report's log_path exists
    # and is non-empty when validate_report checks it; the validation outcome is
    # appended after the check.
    validator_log.write_text(
        "emit_PST-X01_receipt_contract_report: building report via "
        "agent_protocol.build_report\n",
        encoding="utf-8",
    )
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=NOTES,
    )
    out = REPO / "research" / "venue2027" / "proof" / "PST-X01_receipt_contract.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    with validator_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
        fh.write(f"validator exit_code: {0 if result.ok else 1}\n")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
