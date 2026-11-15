"""Emit the DSN-X06_reconcile_journal task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "6fe5fe193a5a55f456f163a853c1b2c41c0c869f"

CHANGED = [
    "evaluation/venue2027/dsn/reconcile_journal.py",
    "evaluation/venue2027/dsn/test_reconcile_journal.py",
    "research/venue2027/proof/DSN-X06_reconcile_journal.json",
    "research/venue2027/proof/logs/DSN-X06_reconcile_journal.pytest.log",
    "research/venue2027/proof/logs/DSN-X06_reconcile_journal.ruff.log",
    "research/venue2027/proof/logs/DSN-X06_reconcile_journal.suite.log",
    "research/venue2027/proof/logs/DSN-X06_reconcile_journal.validator.log",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-X06_reconcile_journal",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_reconcile_journal.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X06_reconcile_journal.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dsn/reconcile_journal.py "
                    "evaluation/venue2027/dsn/test_reconcile_journal.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X06_reconcile_journal.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X06_reconcile_journal.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dsn/reconcile_journal.py",
            "evaluation/venue2027/dsn/test_reconcile_journal.py",
            "research/venue2027/proof/logs/DSN-X06_reconcile_journal.pytest.log",
            "research/venue2027/proof/logs/DSN-X06_reconcile_journal.ruff.log",
            "research/venue2027/proof/logs/DSN-X06_reconcile_journal.suite.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task DSN-X06_reconcile_journal (RQ2) for DSN 2027 (Recoverable Safety "
            "Journals for Crash-Consistent AI-Mediated Health-State Mutations). "
            "evaluation/venue2027/dsn/reconcile_journal.py implements the reconciliation "
            "routine over the three durable views read after bounded recovery -- the "
            "committed clinical row (ClinicalView), the immutable versioned decision "
            "receipt ledger (LedgerView) and the transactional outbox with partial-effect "
            "delivery receipts (OutboxView): reconcile(clinical, ledger, outbox) -> "
            "ReconcileVerdict returns exactly one of CONSISTENT / REPAIRABLE / "
            "IRRECONCILABLE / INDETERMINATE with a stable reason code (26-code registry) "
            "and a JSON-serializable body version-pinned to "
            "clara.dsn.reconcile-journal-v1. Positive outcomes: CONSISTENT only when all "
            "present views carry matching, well-formed evidence for one operation "
            "(CONSISTENT_ALL_VIEWS_AGREE with the applied effect receipt digest, or "
            "CONSISTENT_PENDING_DELIVERY separating storage commit from downstream "
            "delivery, DSN-CASE-07); durable success is NEVER invented -- a missing "
            "delivery receipt never counts as an applied effect, a committed row alone "
            "(missing ledger) is never CONSISTENT, and no HTTP ACK or non-durable signal "
            "is admissible evidence. REPAIRABLE carries an explicit, deterministic, "
            "idempotent repair plan (ordered RepairSteps from the frozen action registry "
            "MARK_LEDGER_COMMITTED / ENQUEUE_OUTBOX / RECORD_DELIVERY, keyed by the "
            "immutable operation ID and bound to the committed row version): the canonical "
            "missing-outbox-row-with-committed-ledger case maps to "
            "REPAIRABLE_MISSING_OUTBOX with a single ENQUEUE_OUTBOX step; a missing ledger "
            "with a committed row maps to REPAIRABLE_MISSING_LEDGER (row is the sole "
            "anchor, receipt stamped from it); tests simulate idempotent plan application "
            "step-by-step to convergence at CONSISTENT, and re-applying a step is a no-op. "
            "IRRECONCILABLE covers positive cross-view contradictions -- ledger row_version "
            "or stored transition digest disagreeing with the committed row "
            "(IRRECONCILABLE_ROW_VERSION_MISMATCH / IRRECONCILABLE_DIGEST_MISMATCH, "
            "DSN-CASE-06 tamper), non-ACCEPT ledger decision, cross-view operation-ID "
            "mismatch, divergent effect digests across duplicate deliveries (DSN-CASE-04), "
            "orphan ledger / orphan outbox without a committed row -- and never carries a "
            "repair plan, so contradicting evidence is never mechanically laundered. "
            "INDETERMINATE is the fail-closed default and is never coerced to CONSISTENT "
            "or a safe rejection: corrupt views (tamper/torn write), timestamp-ordering "
            "anomalies (evidence after the reconciler horizon, receipt/outbox before the "
            "WAL commit, delivery before the outbox record), the all-views-absent picture, "
            "malformed views (typed invalid_fields) and malformed governance inputs all "
            "stay INDETERMINATE with stable reason codes; reconcile is wrapped in a "
            "fail-closed guard so an unexpected internal error yields "
            "INDETERMINATE/INTERNAL_RECONCILIATION_ERROR instead of raising. Purity: "
            "identical inputs yield identical verdicts (sha256-stable via verdict_sha256), "
            "no hidden clock, no randomness, no I/O, no provider calls; logical timestamps "
            "only; synthetic digests only (no patient data). 26 tests passed "
            "(test_reconcile_journal.py), full evaluation/venue2027/ suite 1403 passed, "
            "uvx ruff@0.7.1 check clean. source_sha_after records the base commit "
            "6fe5fe19 per sibling convention (DSN-X01, DSN-X02); the single task commit "
            "SHA is created immediately after this report and reported in the handoff. "
            "Baseline parity NOT_APPLICABLE (candidate reconciliation routine; arms B0-B3 "
            "execute in DSN-X03/X04/X05 benchmarking). Dependencies DSN-oracle and "
            "SH-r4_ci_gate PASS verified in research/venue2027/STATE/completion.json "
            "before start."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-X06_reconcile_journal.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-X06_reconcile_journal",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-X06_reconcile_journal.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
