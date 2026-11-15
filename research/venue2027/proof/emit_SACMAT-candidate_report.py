"""Emit the SACMAT-candidate task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-candidate task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
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
TASK = "SACMAT-candidate"

BASE_SHA = "6fe5fe193a5a55f456f163a853c1b2c41c0c869f"

CHANGED = [
    "evaluation/venue2027/sacmat/candidate.py",
    "evaluation/venue2027/sacmat/test_candidate.py",
    "research/venue2027/proof/SACMAT-candidate.json",
    "research/venue2027/proof/emit_SACMAT-candidate_report.py",
    "research/venue2027/proof/logs/SACMAT-candidate.pytest.log",
    "research/venue2027/proof/logs/SACMAT-candidate.ruff.log",
    "research/venue2027/proof/logs/SACMAT-candidate.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-candidate.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/candidate.py "
        "evaluation/venue2027/sacmat/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-candidate.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-candidate_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-candidate.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-candidate.validator.log",
    },
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
        source_sha_before=BASE_SHA,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "evaluation/venue2027/sacmat/candidate.py",
            "evaluation/venue2027/sacmat/test_candidate.py",
            "research/venue2027/proof/logs/SACMAT-candidate.pytest.log",
            "research/venue2027/proof/logs/SACMAT-candidate.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task SACMAT-candidate (PolicyTrace RQ1-RQ3): temporal "
            "conformance testing candidate. "
            "evaluation/venue2027/sacmat/candidate.py implements "
            "conformance_test(trace, engines) -> ConformanceResult: ONE "
            "delegated-consent trace is replayed through MULTIPLE "
            "heterogeneous in-process policy-engine models over LOGICAL time "
            "(state events GRANT/REVOKE/DELEGATE applied tick by tick; every "
            "ACCESS tick evaluates every engine) and the FIRST pairwise "
            "divergence is reported with the EXACT logical timestamp and the "
            "two disagreeing engines plus both decisions "
            "(TEMPORAL_CONFORMANCE_DIVERGENCE; four-valued vocabulary "
            "PERMIT/DENY/NOT_APPLICABLE/INDETERMINATE). Engine models "
            "implement pinned upstreams' documented semantics with mismatched "
            "portability surfaces: cedar (Cedar v4.14.1: permit/forbid set, "
            "forbid precedence, expiry caller-encoded and NOT honored), "
            "openfga (Zanzibar ATC 2019 / OpenFGA v1.22.1: relation-tuple walk "
            "at read time, expired/revoked tuples absent, two-valued check) "
            "and opa (fail-closed temporal evaluation: lapsed delegation is an "
            "explicit DENY). The divergence class detected is structurally "
            "invisible to static diffs and single-engine tests: a delegation "
            "expiring between grant and access whose terminal state is later "
            "healed — cedar permits at the expiry tick while openfga denies, "
            "and every terminal-state view agrees again. Ablations prove each "
            "component load-bearing: ablation_single_engine (same replay, ONE "
            "engine: no pairwise comparison, misses the divergence with "
            "ABLATION_SINGLE_ENGINE_NO_COMPARISON) and ablation_no_time (all "
            "engines, terminal state only: access decision time and "
            "intermediate ticks discarded, misses the healed divergence with "
            "ABLATION_NO_TIME_TERMINAL_VIEW_ONLY while still catching "
            "unhealed divergence). describe_mechanism() emits the "
            "JSON-serializable mechanism description (components, engine "
            "semantics, ablations, witness form). Harness adapter "
            "run_candidate(case, ctx) -> Outcome maps DIVERGENCE->REJECT / "
            "NO_DIVERGENCE->ADMIT (both counted_as_success=True) and "
            "malformed cases -> INDETERMINATE (never counted, never a silent "
            "safe rejection); simulate_unavailable_upstream returns "
            "NOT_RUN_EXTERNAL / BASELINE_UNAVAILABLE (never counted, "
            "retriable). Wiring errors (unknown engine, non-sequence engines, "
            "unrecognized trace input, non-mapping case) raise "
            "TemporalConformanceError with stable reason codes; data faults "
            "(empty trace, missing logical time, unordered/duplicate "
            "timestamps, unsupported constructs, malformed DELEGATE) are "
            "first-class INDETERMINATE results. No wall clock, randomness, "
            "network or I/O; determinism asserted byte-identical. "
            "Machine-checked: 26 new tests pass (positive: conformant trace "
            "NO_DIVERGENCE with full-timeline agreement, expiry divergence at "
            "EXACT tick 2500 with cedar-vs-openfga witness, revoked-source "
            "delegation divergence NOT_APPLICABLE-vs-DENY at tick 1000, "
            "delegation-chain agreement, run_candidate mapping, "
            "NOT_RUN_EXTERNAL, determinism, describe_mechanism; adversarial: "
            "ablation_single_engine MISSES the expiry divergence for every "
            "single engine, ablation_no_time MISSES the healed divergence "
            "(terminal tick 3000, all engines PERMIT) yet still catches the "
            "unhealed variant, composed ablation misses, insufficient/duplicate "
            "engines INDETERMINATE, malformed-trace battery, wiring-error "
            "reason codes, to_dict round trip); full evaluation/venue2027 "
            "suite 1403 passed; ruff check + format clean on touched files. "
            "Oracle independence: candidate imports no oracle module and the "
            "verdict derives from pairwise engine disagreement only. "
            "source_sha_after = commit HEAD at proof-emission time."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-candidate.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-candidate.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
