"""Emit the ACNS-funding proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-funding task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-funding"
BASE_SHA = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

CHANGED = [
    "research/venue2027/acns/submission/funding_and_author_check.md",
    "research/venue2027/acns/tests/test_funding_check.py",
    "research/venue2027/proof/ACNS-funding.json",
    "research/venue2027/proof/logs/ACNS-funding.validator.log",
    "research/venue2027/proof/logs/ACNS-funding.pytest.log",
    "research/venue2027/proof/logs/ACNS-funding.ruff.check.log",
    "research/venue2027/proof/logs/ACNS-funding.ruff.format.log",
    "research/venue2027/proof/logs/ACNS-funding.suite.log",
    "research/venue2027/proof/logs/ACNS-funding.shared_regression.log",
    "research/venue2027/proof/logs/ACNS-funding.protocol.log",
]

COMMANDS = [
    {
        "argv": "python3 research/venue2027/_shared/tools/submission_contract.py "
        "research/venue2027/acns/submission/funding_and_author_check.md",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.validator.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_funding_check.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.ruff.check.log",
    },
    {
        "argv": "uvx ruff@0.7.1 format --check "
        "research/venue2027/acns/tests/test_funding_check.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.ruff.format.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.suite.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-funding.shared_regression.log",
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
        notes=(
            "P09 submission/funding readiness artifact for ACNS 2027 (Applied Cryptography and "
            "Network Security, Springer LNCS candidate): "
            "research/venue2027/acns/submission/funding_and_author_check.md declares all ten "
            "REQUIRED_FIELDS as labeled lines (cfp_url, template, page_limit, fee_or_registration, "
            "waiver_path, authorship_and_contribution, conflicts_policy, "
            "simultaneous_submission_policy, verification_status, decision). Every external "
            "CFP/deadline/fee/waiver fact is UNVERIFIED with reason 'live CFP not fetched; "
            "re-verify at submission'; the Springer LNCS proceedings-series attribution is itself "
            "a candidate classification. decision is HOLD (not GO) because verification is "
            "pending; no waiver is claimed as assured or automatic; the SPEC-claimed EUR 1,500 "
            "best student award is recorded as a competitive prize, not pre-acceptance funding "
            "and not a waiver; the action ledger states no submission, registration, fee, or "
            "waiver action was taken and human authorization is required. States the P09 "
            "double-submission refusal policy (same manuscript not under review at ACNS 2027 and "
            "any other venue; P09 STOP signal 'Dual archival submission or invented acceptance' "
            "applies) and an explicit ethics boundary: the study is synthetic-only "
            "(synthetic-acns-2027), the two-independent-human-coder design (threat model TC5) "
            "requires independent ethics review (IRB/REC or equivalent) before coder recruitment "
            "begins, and no inter-rater agreement number may be asserted until coder sessions are "
            "executed and recorded. Internal firewalls carried into submission: IFIP SEC "
            "mechanism distinction per PREVIOUS_ANTI_OVERLAP_MATRIX.md (row 'ACNS SoK') and "
            "publication_overlap_registry.yaml acns.reuses_archive: []. Includes a "
            "sponsor/registration request packet outline (post-acceptance only). Machine-checked: "
            "shared submission_contract validate ok:true (exit 0); 19 new tests pass including "
            "adversarial cases (fee/deadline verified-claim without URL+date refused, lowercase "
            "variant refused because the validator regex is case-insensitive; guaranteed waiver "
            "without source refused; missing REQUIRED field refused; missing "
            "simultaneous-submission policy refused); ACNS suite 81 passed; shared foundations "
            "regression 167 passed; uvx ruff@0.7.1 check and format --check clean. No external "
            "submission or payment action was performed by this agent; artifact derives from the "
            "ACNS SPEC and SH-venue_formats checklist only. source_sha_after = base SHA per "
            "established repo convention (proof report committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-funding.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
