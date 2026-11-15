"""Emit the COMPSAC-X06_coarse_occ task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the COMPSAC-X06_coarse_occ task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "COMPSAC-X06_coarse_occ"
BASE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED = [
    "evaluation/venue2027/compsac/baselines.py",
    "research/venue2027/compsac/tasks/coarse_occ_impl.md",
    "research/venue2027/compsac/tests/test_x06_coarse_occ.py",
    "research/venue2027/proof/COMPSAC-X06_coarse_occ.json",
    "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.ruff.log",
    "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.validator.log",
]

COMMANDS = [
    {
        "argv": (
            "python3 -m pytest -q research/venue2027/compsac/tests/"
            "test_x06_coarse_occ.py evaluation/venue2027/compsac/test_baselines.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/compsac/baselines.py "
            "research/venue2027/compsac/tests/test_x06_coarse_occ.py && "
            "uvx ruff@0.7.1 format --check evaluation/venue2027/compsac/baselines.py "
            "research/venue2027/compsac/tests/test_x06_coarse_occ.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.ruff.log",
    },
]

ARTIFACTS = [
    "evaluation/venue2027/compsac/baselines.py",
    "research/venue2027/compsac/tasks/coarse_occ_impl.md",
    "research/venue2027/compsac/tests/test_x06_coarse_occ.py",
    "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.ruff.log",
]


def main() -> int:
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=ARTIFACTS,
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "COMPSAC-X06_coarse_occ (P03, RQ1 B0-side evidence): formalized and executed "
            "the GLOBAL PROFILE-VERSION OCC comparator through the REAL baseline adapter "
            "run_baseline('global-profile-version-occ', case, ctx) "
            "(evaluation/venue2027/compsac/baselines.py arm B0, FAITHFUL_PORT, no forked "
            "implementation): research/venue2027/compsac/tasks/coarse_occ_impl.md "
            "formalizes the arm (one coarse epoch for the whole clinical profile; "
            "commit aborts GLOBAL_PROFILE_STALE iff any entity version moved since the "
            "transaction's start snapshot — checked over the FULL entity space, never a "
            "max-version proxy), its transition relation, the no-lost-update guarantee "
            "(two same-entity writers cannot both commit; committed histories are "
            "equivalent to fully serial execution) and the FALSE-STALE COST — the "
            "oracle-classified set FS(W) of GLOBAL_PROFILE_STALE aborts whose write "
            "target is disjoint from every previously committed write. Backwards-"
            "compatible fidelity fix in _run_global_profile_occ: commit validation used "
            "a max-version proxy (initial_global < max(versions)) that missed concurrent "
            "commits to lower-versioned entities (an empty care_plan register at v0 "
            "moving under medication_order at v1 left the max unchanged and wrongly "
            "ADMITTED a stale transaction); replaced with exact single-coarse-counter "
            "semantics (current version map != start snapshot over ALL entities). No "
            "signature/outcome-label/reason-code change; the 25 pre-existing "
            "evaluation/venue2027/compsac/test_baselines.py tests stay green. "
            "test_x06_coarse_occ.py (10 tests) imports the REAL adapter and runs n=6 "
            "concurrent writes to DIFFERENT entities of the SAME profile (disjoint "
            "targets, private per-transaction journals as declared reads): (1) B0 "
            "commits only the first transaction and aborts all 5 later ones with "
            "GLOBAL_PROFILE_STALE; (2) the REAL false-stale count is computed by an "
            "independent classifier inside the test (declared schedule + per-tx outcome "
            "records only, never B0 internals) and equals n-1 = 5 exactly — the "
            "recorded avoidable-rejection mass; (3) the SAME schedule/seed under B1 "
            "(silo-style entity readset OCC) and B4 (dependency-complete scope-local "
            "OCC) commits all 6 with ZERO aborts — the RQ1 false-stale differential, "
            "equal config across arms, store states diverge by >= n-1 installs; "
            "(4) X06-CASE-07 counter-fidelity regression pin: an unrelated edit to a "
            "LOWER-versioned entity (care_plan v0->v1 under medication_order v1) moves "
            "the profile epoch and aborts an in-flight transaction (the max() proxy "
            "would have admitted it); (5) X06-CASE-06 honest accounting: a same-entity "
            "write-write collision aborts genuinely and the independent classifier "
            "counts ZERO false-stale for that schedule; (6) single-writer control (no "
            "aborts); adversarial fail-closed controls (malformed schedule -> "
            "EXECUTION_ERROR/SCHEDULE_MALFORMED; byte-identical determinism; equal-"
            "config discipline; X06_COARSE_OCC_SPEC_VERSION 1.0.0 pins "
            "COMPSAC_BASELINES_VERSION 1.0.0). 35 passed total (10 new + 25 baseline "
            "suite); uvx ruff@0.7.1 check + format --check clean; uvx mypy@1.13.0 "
            "--ignore-missing-imports: 0 errors in the new test file, the 4 remaining "
            "errors in baselines.py are pre-existing at the base commit (verified by "
            "git stash). source_sha_after records the base commit 06125d52 per sibling "
            "convention (COMPSAC-baselines/POPETS-X05); the single task commit SHA is "
            "created immediately after this report and reported in the handoff. "
            "Baseline parity PASS: B0 vs B1/B4 differential measured on the identical "
            "schedule (5 false-stale aborts vs 0); forbidden_commits = 0 everywhere. "
            "Next ready tasks: COMPSAC-X04_pg_ssi, COMPSAC-X05_silo_occ."
        ),
    )

    # Proof file lives at research/venue2027/proof/COMPSAC-X06_coarse_occ.json.
    out_path = REPO / "research/venue2027/proof/COMPSAC-X06_coarse_occ.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path = REPO / "research/venue2027/proof/logs/COMPSAC-X06_coarse_occ.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
