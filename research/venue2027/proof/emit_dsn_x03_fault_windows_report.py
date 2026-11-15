"""Emit the DSN-X03_fault_windows task proof report via agent_protocol.build_report."""

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
    "evaluation/venue2027/dsn/fault_windows.py",
    "evaluation/venue2027/dsn/test_fault_windows.py",
    "research/venue2027/proof/logs/DSN-X03_fault_windows.pytest.log",
    "research/venue2027/proof/logs/DSN-X03_fault_windows.ruff.log",
    "research/venue2027/proof/logs/DSN-X03_fault_windows.suite.log",
    "research/venue2027/proof/logs/DSN-X03_fault_windows.selfcheck.log",
    "research/venue2027/proof/DSN-X03_fault_windows.json",
]


def main() -> int:
    sha_after = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    report = ap.build_report(
        task_id="DSN-X03_fault_windows",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/dsn/test_fault_windows.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X03_fault_windows.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/dsn/fault_windows.py "
                    "evaluation/venue2027/dsn/test_fault_windows.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X03_fault_windows.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X03_fault_windows.suite.log",
            },
            {
                "argv": "python3 -m evaluation.venue2027.dsn.fault_windows",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/DSN-X03_fault_windows.selfcheck.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/dsn/fault_windows.py",
            "evaluation/venue2027/dsn/test_fault_windows.py",
            "research/venue2027/proof/logs/DSN-X03_fault_windows.pytest.log",
            "research/venue2027/proof/logs/DSN-X03_fault_windows.ruff.log",
            "research/venue2027/proof/logs/DSN-X03_fault_windows.suite.log",
            "research/venue2027/proof/logs/DSN-X03_fault_windows.selfcheck.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task DSN-X03_fault_windows (RQ1): deterministic fault-injection "
            "controller enumerating the named crash cut points across one commit "
            "lifecycle for the DSN 2027 recoverable-safety-journal study. "
            "evaluation/venue2027/dsn/fault_windows.py defines the canonical five-stage "
            "lifecycle (INTENT -> WAL_WRITE -> APPLY -> PERSIST_RECEIPT -> OUTBOX_DELIVER, "
            "mapping the manifest barriers SQL flush / commit ACK / outbox enqueue / "
            "broker publish / consumer ack) and five named windows: BEFORE_WAL (anchor "
            "WAL_WRITE, DSN-CASE-02: nothing durable anywhere), AFTER_WAL_BEFORE_APPLY "
            "(anchor APPLY, unapplied WAL is not a committed mutation), "
            "AFTER_APPLY_BEFORE_RECEIPT (anchor PERSIST_RECEIPT, DSN-CASE-03 "
            "unknown-response reconciliation), AFTER_RECEIPT (anchor OUTBOX_DELIVER, "
            "DSN-CASE-03/07 pending delivery) and DOUBLE_FAULT (two crashes in one "
            "lifecycle: first crash at the earliest reachable single-window barrier, "
            "deterministic restart, second CrashInjected crash_number=2 propagates to "
            "the caller; repeated kill/restart adversarial control). Injection uses "
            "named synchronization barriers, never sleep-based causal guesses and no "
            "randomness: the LifecycleRun recorder arms one window; crossing the armed "
            "anchor barrier raises CrashInjected inside record_stage at that exact cut "
            "point, the anchor stage is never recorded, and the crash is sticky for the "
            "attempt (a SIGKILLed process cannot record further stages). API: "
            "enumerate_fault_windows(ops) -> list[FaultWindow] (manifest signature "
            "enumerate_windows alias provided) and run_with_window(window, fn, "
            "lifecycle=...), which never returns normally: it injects or refuses. "
            "Fail-closed refusal semantics with 10 stable reason codes (UNKNOWN_STAGE, "
            "DUPLICATE_STAGE, DUPLICATE_WINDOW, WINDOW_CATALOG_MISMATCH, "
            "WINDOW_NOT_REACHABLE, UNORDERED_LIFECYCLE, DOUBLE_FAULT_UNREACHABLE, "
            "EMPTY_LIFECYCLE, LIFECYCLE_REQUIRED, MALFORMED_CRASH_RECORD): a window "
            "whose anchor barrier is absent from the lifecycle is refused at "
            "enumeration AND injection time rather than silently skipped (no partial "
            "enumeration can masquerade as a complete schedule); a lifecycle that "
            "completes without crossing the armed barrier is refused dynamically "
            "(missed injection can never count as a pass); duplicate windows in the "
            "catalog are detected via WINDOW_ORDER/WINDOW_ANCHOR integrity checks "
            "before every enumeration; duplicate, unknown and reordered stages are "
            "refused; DOUBLE_FAULT without a reachable barrier or without an explicit "
            "lifecycle is refused. FaultWindow/LifecycleRun/CrashInjected are typed, "
            "JSON-serializable, with lossless to_dict/from_dict round-trips; the "
            "CrashInjected exception carries the ordered run transcript so callers "
            "reconstruct the durable prefix without introspecting candidate internals "
            "(oracle independence). test_fault_windows.py: 35 tests (stdlib pytest "
            "only, no third-party deps, no DB/network) -- positive: full lifecycle "
            "enumerates all five windows exactly once in canonical order with "
            "documented anchors and CASE_MATRIX refs; every single window actually "
            "injected at its barrier with anchor stage never recorded and all prior "
            "stages recorded on the transcript; DOUBLE_FAULT injects two observable "
            "crashes (harness observes crash #1, records recovery/restart, crash #2 "
            "propagates); truncation of the lifecycle refuses exactly the unreachable "
            "window; enumeration and injection are deterministic (identical transcripts "
            "across repeats, JSON-serializable); -- negative/adversarial: unreachable "
            "window refused (WINDOW_NOT_REACHABLE, static + dynamic), duplicate-window "
            "catalog corruption detected (DUPLICATE_WINDOW / WINDOW_CATALOG_MISMATCH "
            "via monkeypatched WINDOW_ORDER and WINDOW_ANCHOR), duplicate/unknown/"
            "reordered/empty lifecycles refused, sticky crash and no double-record "
            "within one attempt, DOUBLE_FAULT never silent when no second crash "
            "occurs, malformed payloads refused with stable codes. 35 passed in ~0.4s; "
            "full evaluation/venue2027 suite 1412 passed; uvx ruff@0.7.1 check clean "
            "on both files; module self-check (python3 -m "
            "evaluation.venue2027.dsn.fault_windows) injects all five windows with "
            "exit 0. source_sha_after records the base commit 6fe5fe19 per sibling "
            "convention (DSN-X01, DSN-X02); the single task commit SHA is created "
            "immediately after this report and reported in the handoff. Baseline "
            "parity NOT_APPLICABLE (injection controller layer; arms B0-B3 execute in "
            "DSN-X04..X06, kill driver is DSN-X07). Dependencies DSN-oracle and "
            "SH-r4_ci_gate PASS verified in research/venue2027/STATE/completion.json "
            "before start. Windows enumerated on the full canonical lifecycle: "
            "BEFORE_WAL, AFTER_WAL_BEFORE_APPLY, AFTER_APPLY_BEFORE_RECEIPT, "
            "AFTER_RECEIPT, DOUBLE_FAULT (anchors WAL_WRITE, APPLY, PERSIST_RECEIPT, "
            "OUTBOX_DELIVER, WAL_WRITE respectively). Next ready tasks: DSN-X04_"
            "outbox_reference, DSN-X05_workflow_reference, DSN-X06_reconcile_journal."
        ),
    )

    out_path = REPO / "research/venue2027/proof/DSN-X03_fault_windows.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="DSN-X03_fault_windows",
    )
    log_path = REPO / "research/venue2027/proof/logs/DSN-X03_fault_windows.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
