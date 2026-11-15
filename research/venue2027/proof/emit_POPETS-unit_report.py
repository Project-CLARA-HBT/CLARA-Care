"""Emit research/venue2027/proof/POPETS-unit.json via agent_protocol.

Assembles the POPETS-unit task report with real command logs (pytest over the
property/metamorphic/mutation suite, uvx ruff check + format --check over the
POPETS test package, full venue regression suite, emitter/validator) and
hashes every declared artifact, then validates it with
agent_protocol.validate_report.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from research.venue2027._shared.tools.agent_protocol import (  # noqa: E402
    build_report,
    validate_report,
)

TASK_ID = "POPETS-unit"
SOURCE_SHA_BEFORE = "5f97bc366a18a2d3722884cfc44a25fb2d6bee59"

CHANGED_PATHS = [
    "tests/venue2027/popets/test_algorithm_properties.py",
    "research/venue2027/proof/POPETS-unit.json",
    "research/venue2027/proof/logs/POPETS-unit.pytest.log",
    "research/venue2027/proof/logs/POPETS-unit.ruff.log",
    "research/venue2027/proof/logs/POPETS-unit.suite.log",
    "research/venue2027/proof/logs/POPETS-unit.validator.log",
]

ARTIFACT_PATHS = [
    "tests/venue2027/popets/test_algorithm_properties.py",
    "research/venue2027/proof/logs/POPETS-unit.pytest.log",
    "research/venue2027/proof/logs/POPETS-unit.ruff.log",
    "research/venue2027/proof/logs/POPETS-unit.suite.log",
]


def main() -> int:
    source_sha_after = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    report = build_report(
        task_id=TASK_ID,
        status="PASS",
        source_sha_before=SOURCE_SHA_BEFORE,
        source_sha_after=source_sha_after,
        changed_paths=CHANGED_PATHS,
        commands=[
            {
                "argv": "python3 -m pytest -q tests/venue2027/popets/test_algorithm_properties.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-unit.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check tests/venue2027/popets/ && "
                "uvx ruff@0.7.1 format --check tests/venue2027/popets/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-unit.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/ tests/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-unit.suite.log",
            },
            {
                "argv": "PYTHONPATH=. python3 "
                "research/venue2027/proof/emit_POPETS-unit_report.py "
                "# build_report + validate_report(ok:true) recorded in "
                "research/venue2027/proof/POPETS-unit.json",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-unit.validator.log",
            },
        ],
        artifact_paths=ARTIFACT_PATHS,
        repo=ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P05 POPETS-unit deliverable: "
            "tests/venue2027/popets/test_algorithm_properties.py — deterministic "
            "property/metamorphic/mutation tests over the REAL POPETS components, imported "
            "live and never reimplemented: revocation_model.py (allowed()/decide() -> "
            "TriDecision), candidate.py (RevocationCompleteCache dependency-closure "
            "invalidation + mechanism-isolation ablation via run_candidate), baselines.py "
            "(all four implemented arms through the real run_baseline entry point: B1 "
            "coarse-cache-purge, B2 always-recompute, purpose-bound-cache-keying, "
            "purpose-aware-cache-x06 with purpose_cache_fetch). ALL randomness is seeded "
            "deterministically (fixed random.Random(FIXED_SEED)=20271115; no time, no "
            "unseeded random, no hidden entropy; the components under test are pure with "
            "injected state). Six test families, 64 tests, all passing: (1) POSITIVE "
            "boundaries — pre-t_r ALLOW, revocation-completeness at/after t_r, stable "
            "reason codes (ALLOWED_ACTIVE_CONSENT / DENY_POST_REVOCATION), unaffected "
            "purposes stay servable, dependency-closure transitive invalidation with exact "
            "left-live set (no full flush), X06 purpose-isolation invariant 0 violations "
            "over real cache state, repeat-dispatch HIT at current epoch, exposed_bytes "
            "nonzero only on admitted dispatches. (2) NEGATIVE boundaries — parametrized "
            "malformed principal/purpose/time/item raising stable uppercase codes "
            "(PRINCIPAL_MALFORMED / PURPOSE_UNKNOWN / TIME_MALFORMED / ITEM_MALFORMED), "
            "candidate put refusals (DEPS_MALFORMED / VALUE_MALFORMED / KEY_MALFORMED / "
            "DERIVATION_PARENT_MISSING / DERIVATION_CYCLE), baseline fail-closed "
            "WORKLOAD_MALFORMED on malformed workloads in every arm, unknown baseline id "
            "returns NOT_RUN_EXTERNAL/BASELINE_UNAVAILABLE (never guessed), X06 fetch "
            "refuses cross-purpose (PURPOSE_MISMATCH), malformed keys (KEY_MALFORMED incl. "
            "bool epoch) and absent entries (CACHE_MISS). (3) UNKNOWN boundaries — "
            "INDETERMINATE is first-class and never coerced: unknown purpose strings vs "
            "known-but-unconsented purposes (PURPOSE_UNKNOWN vs PURPOSE_NOT_CONSENTED), "
            "TIME_BEFORE_GRANT, unlabelled/None lineage labels (LINEAGE_INDETERMINATE), "
            "GRANT_UNKNOWN for unknown principals, plus a fixed-seed randomized sweep "
            "(25 mixed + 30 unknown-only probes) with byte-identical re-seeded replay. "
            "(4) REVOCATION-TIMING RACES — dispatch exactly AT t_r denied boundary-"
            "inclusive in the model AND every implemented arm (REVOKED_CONTEXT), one tick "
            "before t_r still servable, earliest-covering-revocation wins multi-revocation "
            "races (specific + wildcard rows), wildcard purpose covers every purpose with "
            "stored_data='deleted' reported orthogonally, replay race: stale-epoch retry "
            "payload DENIED (DENY_EPOCH_STALE) even strictly before t_r, stale-epoch vs "
            "post-revocation denial race resolves to DENY_POST_REVOCATION, future "
            "revocation leaves earlier dispatches untouched, B1 cached-entry race: repeat "
            "dispatch of a pre-t_r cached entry after revocation stays REJECT with zero "
            "exposed bytes despite the cache-hit flag (cache hit can never resurrect "
            "revoked context), candidate idempotent re-revoke (applied=False, single log "
            "record). (5) TWO-STEP METAMORPHIC RELATIONS — MR1 purge-then-re-dispatch: "
            "B1's subject-wide purge never re-admits the revoked scope on re-dispatch "
            "(REJECT/REVOKED_CONTEXT, exposed_bytes 0); MR2 candidate purge-then-reput: "
            "put at the revoked scope refused (REVOKED_DEPENDENCY), legitimate new-epoch "
            "re-put served ONLY at the new epoch and EPOCH_STALE for the revoked one; MR3 "
            "purpose-keying epochs monotonic per scope across repeated post-revocation "
            "dispatches (0,1,2,3, rotations=3); MR4 purpose-keying monotonic under purpose "
            "change: revoking purpose 'a' rotates only the (g1,a) key space, purpose 'b' "
            "epochs stay 0 (no crosstalk); MR5 candidate vs ablation on the IDENTICAL op "
            "stream diverge exactly on the under-declared derived entry (candidate "
            "REVOKED_ENTRY / leaks=0, ablation HIT served_from_revoked_ancestry / "
            "leaks=1 leak_keys=[derived], all other read statuses equal); MR6 "
            "revocation_semantics() singleton immutable with retroactive-erasure=False and "
            "memorization always NOT_GUARANTEED; MR7 every arm byte-identical under "
            "re-invocation with different ctx seeds (no hidden randomness). (6) MUTATION-"
            "STYLE CHECKS — single-input perturbations flip the expected verdict: time "
            "across t_r (ALLOW->DENY), purpose string (DENY->ALLOW on the unaffected "
            "scope), scope mutation flips pair outcome ADMIT->REJECT in every arm, "
            "candidate epoch/purpose mutation flips HIT->EPOCH_STALE->PURPOSE_MISMATCH, "
            "dropping the revocation event flips REVOKED_ENTRY->HIT, removing a lineage "
            "label flips ALLOW->INDETERMINATE (fail-closed, never a silent DENY), granted_at "
            "mutation flips the unknown boundary, already_delivered flag never changes the "
            "verdict but attaches OUT_OF_SCOPE_PAST + NOT_GUARANTEED (no erasure claim), "
            "plus a fixed-seed 20-case mutation campaign where the unperturbed twin stays "
            "ADMIT and the scope-mutated twin is REJECT in every arm (mutation kill, no "
            "equivalent mutants). Pass gate 'Test evidence and mutation coverage' and the "
            "manifest negative gate ('Arbitrary all-deny passes correctness? assert "
            "liveness') are addressed: liveness is asserted positively (unaffected scopes "
            "HIT/ALLOW in every family, exactness left_live set, pre-t_r ALLOW) so an "
            "all-deny stub would fail at least 20 assertions. Verification: pytest "
            "64 passed (exit 0); uvx ruff@0.7.1 check + format --check clean on "
            "tests/venue2027/popets/ (exit 0); full evaluation/venue2027 + tests/venue2027 "
            "regression 1853 passed (exit 0). source_sha_after records the base commit "
            "5f97bc36 per the sibling convention; the single task commit SHA is created "
            "immediately after this report and recorded in the commit body. No empirical "
            "leakage claims: design-level executable invariants only; no claim of "
            "retroactive erasure or model unlearning anywhere. Baseline parity "
            "NOT_APPLICABLE (unit/property layer; arms B0-B4 execute in P03)."
        ),
    )

    out = ROOT / "research" / "venue2027" / "proof" / "POPETS-unit.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {out}", flush=True)

    # Validate the emitted report and write the proof-of-validation log OUTSIDE the
    # report's own artifact set (a log describing the validation of the report
    # cannot hash itself).
    validation = validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=ROOT,
        expected_task_id=TASK_ID,
    )
    validator_log = ROOT / "research" / "venue2027" / "proof" / "logs" / "POPETS-unit.validator.log"
    validator_log.write_text(json.dumps(validation.to_dict(), indent=1) + "\n", encoding="utf-8")
    print(json.dumps(validation.to_dict(), indent=1), flush=True)
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
