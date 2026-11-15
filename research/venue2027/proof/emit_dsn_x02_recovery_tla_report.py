"""Emit the DSN-X02_recovery_tla task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED = [
    "research/venue2027/dsn/formal/recovery.tla",
    "research/venue2027/dsn/formal/Recovery.cfg",
    "research/venue2027/dsn/tests/test_recovery_tla.py",
    "research/venue2027/proof/logs/DSN-X02_recovery_tla.pytest.log",
    "research/venue2027/proof/logs/DSN-X02_recovery_tla.ruff.log",
    "research/venue2027/proof/logs/DSN-X02_recovery_tla.validator.log",
    "research/venue2027/proof/DSN-X02_recovery_tla.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-X02_recovery_tla",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q research/venue2027/dsn/tests/" "test_recovery_tla.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/" "DSN-X02_recovery_tla.pytest.log"),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check research/venue2027/dsn/tests/" "test_recovery_tla.py"
                ),
                "exit_code": 0,
                "log_path": ("research/venue2027/proof/logs/DSN-X02_recovery_tla.ruff.log"),
            },
        ],
        artifact_paths=[
            "research/venue2027/dsn/formal/recovery.tla",
            "research/venue2027/dsn/formal/Recovery.cfg",
            "research/venue2027/dsn/tests/test_recovery_tla.py",
            "research/venue2027/proof/logs/DSN-X02_recovery_tla.pytest.log",
            "research/venue2027/proof/logs/DSN-X02_recovery_tla.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 task DSN-X02_recovery_tla (RQ1): bounded TLA+ model of the joint "
            "recoverability contract for AI-mediated health-state mutations. "
            "research/venue2027/dsn/formal/recovery.tla composes the four mandated "
            "concern planes -- consumer replay (ConsumerReplay: at-least-once outbox "
            "delivery bounded by MaxRedelivery=3, i.e. the DSN-CASE-04 triple broker "
            "replay, with idempotent effect application: a redelivered op never "
            "appends a second effect), consent mutation (ConsentRevoke/ConsentRenew "
            "bumping a monotone consentEpoch, DSN-CASE-05 governance race), kernel "
            "commit (KernelCommit: durable clinical-row write re-checking consent "
            "under the commit lock; revocation in the authorization window aborts "
            "with a durable REJECTED receipt and no forbidden write) and receipt "
            "persistence (PersistReceipt: versioned per-op decision receipt with "
            "captured consent epoch). Crash(p) fires at ANY pipeline transition and "
            "loses only volatile state (program counter, broker ledger), so "
            "disagreement arises purely from the order of durable writes. "
            "Recovery(p) is the reconciler deciding from durable evidence only with "
            "the three oracle labels: committed row + committed receipt -> "
            "consistent; committed row + 'none' receipt (crash window between "
            "KernelCommit and PersistReceipt, DSN-CASE-03) -> 'reconciled': the row "
            "is durable ground truth, receipt stamped committed and outbox "
            "(re)queued; row/receipt disagreement incl. Tamper corruption "
            "(DSN-CASE-06) -> 'indeterminate' (ambiguous evidence normalized to "
            "INDETERMINATE, never a silent successful state); durable REJECTED "
            "stands; nothing durable -> no_effect (retry under the same immutable "
            "op id is safe). Invariants: TypeOK, NoPhantomSuccess (committed "
            "receipt implies committed clinical row), ExactlyOnceEffect (effects "
            "log injective per op, grounded in box and committedOps), "
            "ReceiptConsistency (receipt epochs <= consent epoch, rejected never "
            "coexists with committed row, outbox grounded in committed rows), "
            "OutboxIsGrounded, RecoveryFailClosed; temporal PROPERTY "
            "NoCommittedThenLost (committed rows are never erased). "
            "Recovery.cfg pins the required bounds OpCount=3 (2..4), Procs=2 "
            "(1..3), MaxEpochs=2, MaxRedelivery=3, checks Spec = Init /\\ "
            "[][Next]_vars /\\ Fairness with repeatable fairness settings "
            "(WF_vars(Recovery(p)), WF_vars(ConsumerReplay), WF_vars(Authorize(p)); "
            "Crash/Tamper deliberately unfair) and documents -dumptrace "
            "counterexample export; no symmetry declared (symmetry could mask "
            "row-vs-receipt mismatches). "
            "test_recovery_tla.py (17 stdlib tests, no third-party deps) parses the "
            ".tla/.cfg: required definitions (Init/Next/Recovery/NoPhantomSuccess/"
            "ExactlyOnceEffect/TypeOK/ReceiptConsistency/OutboxIsGrounded/"
            "RecoveryFailClosed/NoCommittedThenLost), the four concern planes, "
            "Next-enables-all-core-actions, >=2 substantive invariants (6 declared, "
            "all defined in the spec), temporal property declared, injectivity "
            "clause of ExactlyOnceEffect and row-grounding of NoPhantomSuccess, "
            "Recovery fail-closed labels incl. INDETERMINATE normalization, "
            "adversarial Crash+Tamper actions, cfg bounds within the ASSUME ranges "
            "(2..4 ops, 1..3 procs), SPECIFICATION Spec + fairness coverage "
            "(Crash excluded from fairness), documented tlc2.TLC/-dumptrace export, "
            "module header version v1.0.0, and a truthful TLC execution probe: the "
            "test would execute java -cp <jar> tlc2.TLC if a distribution were "
            "present, but in this environment none is (no java runtime, no "
            "tla2tools.jar, TLA_TOOLS_JAR unset), so TLC model checking is "
            "recorded as TLC NOT_RUN -- no model-checking pass is claimed anywhere; "
            "the spec+config are complete and runnable as-is wherever "
            "java+tla2tools.jar exist. 17 passed; uvx ruff@0.7.1 check clean. "
            "source_sha_after records the base commit 06125d52 per sibling "
            "convention (COMPSAC-X01, AIME-X02); the single task commit SHA is "
            "created immediately after this report and reported in the handoff. "
            "Baseline parity NOT_APPLICABLE (formal semantics layer; arms B0-B3 "
            "execute in DSN-X04..X06). Dependency DSN-schema PASS verified in "
            "STATE/completion.json before start. Next ready tasks: DSN-X03_"
            "fault_windows, DSN-X04_outbox_reference, DSN-X05_workflow_reference."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-X02_recovery_tla.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-X02_recovery_tla",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-X02_recovery_tla.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
