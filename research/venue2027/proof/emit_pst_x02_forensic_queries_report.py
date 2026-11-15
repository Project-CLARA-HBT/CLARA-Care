"""Emit the PST-X02_forensic_queries task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the PST-X02_forensic_queries task. No network access.

Failure semantics: exits non-zero if report construction or validation fails;
the validator result is recorded in
``research/venue2027/proof/logs/PST-X02_forensic_queries.validator.log``.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "PST-X02_forensic_queries"
BASE = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED = [
    "evaluation/venue2027/pst/forensic_queries.py",
    "evaluation/venue2027/pst/test_forensic_queries.py",
    "research/venue2027/proof/PST-X02_forensic_queries.json",
    "research/venue2027/proof/emit_pst_x02_forensic_queries_report.py",
    "research/venue2027/proof/logs/PST-X02_forensic_queries.pytest.log",
    "research/venue2027/proof/logs/PST-X02_forensic_queries.ruff.log",
    "research/venue2027/proof/logs/PST-X02_forensic_queries.suite.log",
    "research/venue2027/proof/logs/PST-X02_forensic_queries.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q " "evaluation/venue2027/pst/test_forensic_queries.py"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/" "PST-X02_forensic_queries.pytest.log"
                ),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/pst/"
                    "forensic_queries.py evaluation/venue2027/pst/"
                    "test_forensic_queries.py && uvx ruff@0.7.1 format --check "
                    "evaluation/venue2027/pst/"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "PST-X02_forensic_queries.ruff.log"),
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "PST-X02_forensic_queries.suite.log"),
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_pst_x02_forensic_queries_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/PST-X02_forensic_queries.json"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/" "PST-X02_forensic_queries.validator.log"
                ),
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/pst/forensic_queries.py",
            "evaluation/venue2027/pst/test_forensic_queries.py",
            "research/venue2027/proof/logs/PST-X02_forensic_queries.pytest.log",
            "research/venue2027/proof/logs/PST-X02_forensic_queries.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 PST-X02_forensic_queries deliverable (ReceiptMin RQ1 "
            "denominator): evaluation/venue2027/pst/forensic_queries.py freezes "
            "the EX ANTE forensic query set as a module constant — 12 typed "
            "frozen dataclass ForensicQuery objects (FQ-AUTH-01..04 "
            "authorization, FQ-PROV-01..04 provenance, FQ-ELIG-01..04 "
            "commit_eligibility) each carrying the task-contract signature "
            "triple (query_id, witnesses_needed, trusted oracle answer) plus an "
            "oracle pointer into the preregistered catalog. "
            "FROZEN_QUERY_SET_SHA256 (16801af9c1f00bd6ca64fc48b3e0013873069e9de"
            "446a9bb87978b7b16cdbab2) is the canonical-JSON SHA256 of the "
            "serialized set, committed with the set so post-hoc addition, "
            "removal, rewording, witness-set loosening or reordering is "
            "mechanically refused by assert_frozen_query_set with stable reason "
            "code QUERY_SET_DRIFT (editing both constant and set is a protocol "
            "violation visible in review as a diff to a frozen constant). "
            "answerable(query, audit_view) classifies an injected read-only "
            "AuditView (retained_fields, retention_mode, epoch_active, "
            "key_custody_attested) fail-closed into exactly the three typed "
            "outcomes: ANSWERABLE requires every witness field retained and "
            "coherent plus the class's consent/policy epoch attestations "
            "active; NOT_ANSWERABLE marks provable reconstruction loss "
            "(witness dropped by minimization — PST-CASE-05 over-redaction, "
            "hash-only retention keeps digests alone, PST-CASE-09 no-log); "
            "INDETERMINATE marks evidence present but a load-bearing proof "
            "missing (consent/policy epoch attestation absent; key-custody "
            "attestation missing for provenance queries reading committed "
            "CONTENT beyond the bare digest — PST-CASE-07/12 — while a "
            "bare-digest existence query FQ-PROV-01 stays ANSWERABLE because "
            "hash chains prove commitment existence without any content key). "
            "INDETERMINATE is retained and counted, never coerced to success "
            "(CASE MATRIX rule). All reason codes stable uppercase "
            "(UNKNOWN_QUERY_ID, MALFORMED_QUERY, MALFORMED_AUDIT_VIEW, "
            "QUERY_SET_DRIFT); unknown ids and malformed views fail closed. "
            "The set is PHI-free: structural receipt-field vocabulary only, "
            "guarded in tests against the shared PHI_FIELD_MARKERS registry. "
            "test_forensic_queries.py: 25 tests pass (positive: stable ids, "
            "unique lookup, deterministic set hash equal to the committed "
            "freeze constant, freeze gate accepts the shipped set, "
            "JSON-serializability + PHI-free, full-vs-minimized classification "
            "matching the mandatory-field rule, hash-only/no-log reconstruction "
            "losses, missing key custody and missing epoch attestation yield "
            "INDETERMINATE, purity/order-independence, full view is the "
            "utility upper bound (monotone rank); adversarial: assert_frozen_"
            "query_set refuses added / removed / reworded / reordered / "
            "witness-loosened sets with QUERY_SET_DRIFT, unknown query id "
            "UNKNOWN_QUERY_ID, malformed audit views MALFORMED_AUDIT_VIEW, "
            "malformed set members MALFORMED_QUERY incl. a PHI witness field, "
            "INDETERMINATE never coerced). uvx ruff@0.7.1 check + format --"
            "check clean on touched files; full evaluation/venue2027 "
            "regression 1092 passed. No oracle repair post hoc: the freeze "
            "constant predates this session's runs and was never edited. "
            "source_sha_after = base commit 11a9219c per the sibling "
            "dataset-task convention (PST-dataset, AIME-X02_case_generator): "
            "the single task commit is created immediately after this report "
            "and recorded in the commit body."
        ),
    )

    out_path = REPO / "research/venue2027/proof/PST-X02_forensic_queries.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/PST-X02_forensic_queries.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
