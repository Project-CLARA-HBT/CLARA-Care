"""Emit the COMPSAC-candidate proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the COMPSAC-candidate task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "COMPSAC-candidate"
BASE_SHA = "11a9219ce0a1d3d523400350abb959c0f56699f2"

CHANGED = [
    "evaluation/venue2027/compsac/candidate.py",
    "evaluation/venue2027/compsac/test_candidate.py",
    "research/venue2027/proof/COMPSAC-candidate.json",
    "research/venue2027/proof/logs/COMPSAC-candidate.pytest.log",
    "research/venue2027/proof/logs/COMPSAC-candidate.ruff.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/compsac/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-candidate.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/compsac/candidate.py evaluation/venue2027/compsac/test_candidate.py && uvx ruff@0.7.1 format --check evaluation/venue2027/compsac/candidate.py evaluation/venue2027/compsac/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/COMPSAC-candidate.ruff.log",
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
            "COMPSAC-candidate (Phase P04, priority; CANDIDATE DESIGN ONLY - no "
            "empirical results, no performance numbers, no win rates): implemented "
            "the dependency-complete optimistic admission candidate at "
            "evaluation/venue2027/compsac/candidate.py behind admit(op, store, scope) "
            "-> AdmissionOutcome (CANDIDATE_ID="
            "clara.compsac.candidate.dependency-complete-scope-local-occ, v1.0.0, "
            "describe_mechanism() exposes the machine-readable design record). "
            "Algorithmic definition: shape-validate -> derive the REQUIRED dependency "
            "closure via an INJECTED oracle (AdmissionScope.dependency_oracle; missing/"
            "refusing/faulting/malformed oracle all fail closed ERROR - never guessed, "
            "never counted as a safe rejection) -> join validation scope (closure "
            "entities + declared reads + declared writes) -> governance register and "
            "GOVERNANCE closure-edge epoch validation first (never omitted even for an "
            "empty domain closure, COMPSAC-CASE-08) -> scope-local per-entity snapshot "
            "version fence with REQUIRED_EDGE_STALE (required edges incl. the omitted "
            "dependency) and WRITE_TARGET_SUPERSEDED (declared write targets) plus "
            "per-entity consent/policy epoch bindings under canonical lock order "
            "(governance anchors, then GOVERNANCE edges, then sorted entities - "
            "deadlock-free, COMPSAC-CASE-06, order-independent) -> install declared "
            "writes version+1 on ADMIT. ABLATION HOOKS (real mechanism axes for P04): "
            "ablation_no_closure(scope) drops the injected closure (declared touch set "
            "only) and ablation_global_version(scope) switches to the single coarse "
            "profile global_epoch fence (B0 semantics, false-stale upper bound). "
            "MUTATION REGISTRY (mutation-adequacy instrument): M1-drop-epoch-validation, "
            "M2-declared-reads-only, M3-ignore-superseded-writes via "
            "admit_with_mutation(); unknown mutation ids fail closed ERROR/"
            "UNKNOWN_MUTATION. Tests (64 passed, unit + property + mutation): "
            "ABLATION CONTRAST SHOWN - the candidate REJECTs the canonical omitted-"
            "dependency write-skew operation (REQUIRED_EDGE_STALE on the concurrently "
            "moved allergy_list edge) while ablation_no_closure() ADMITS the identical "
            "operation on the identical store/snapshot (same mode, smaller fence), "
            "proving the closure is the mechanism; ablation_no_closure still enforces "
            "governance epochs; ablation_global_version false-stales on an UNRELATED "
            "concurrent write (GLOBAL_EPOCH_STALE) that the scope-local candidate "
            "admits (COMPSAC-CASE-01 false-stale witness pair). MUTATION CAUGHT - "
            "M1: consent revoked concurrently, candidate REJECTs vs mutation ADMITs; "
            "M2: write-skew witness, candidate REJECTs vs mutation ADMITs; M3: "
            "superseded write target, candidate REJECTs vs mutation ADMITs; each "
            "mutation is caught as a behavioral differential. Determinism: repeated "
            "admissions identical (full outcome dict + digest); closure-iteration-"
            "order property over 24 seeded frozenset permutations yields one digest; "
            "rejection-monotonicity property holds. Fail-closed controls: missing/"
            "refusing/faulting/malformed oracle -> ERROR with stable reason codes "
            "(CLOSURE_ORACLE_MISSING / CLOSURE_ORACLE_REFUSED incl. injected "
            "ClosureOracleRefusal reason pass-through / CLOSURE_ORACLE_MALFORMED), "
            "UNKNOWN_ENTITY, SNAPSHOT_INCOMPLETE, UNKNOWN_GOVERNANCE_RESOURCE, ERROR "
            "never installs state and is never counted; empty-touch-set op refused "
            "OP_MALFORMED; write-only op stays determined via the injected closure. "
            "Independence preserved: the candidate contains NO closure rules of its "
            "own - completeness of the injected closure (COMPSAC-CASE-04) remains "
            "adjudicated by the independent oracle outside this module; negative-"
            "predicate phantom inserts (COMPSAC-CASE-05) documented as out of scope "
            "for the in-process fence (P05 PostgreSQL comparison). Full compsac "
            "suite regression: 261 passed. source_sha_after = base SHA per "
            "established repo convention (proof report committed together with the "
            "work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "COMPSAC-candidate.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
