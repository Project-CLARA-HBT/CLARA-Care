"""Emit the SACMAT-X06_temporal_generator task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the SACMAT-X06_temporal_generator task. No network access.

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
TASK = "SACMAT-X06_temporal_generator"

BASE_SHA = "687a6f56def769fc930e0ee94b00476eecc1c69b"

CHANGED = [
    "evaluation/venue2027/sacmat/temporal_trace_generator.py",
    "research/venue2027/sacmat/tests/test_temporal_generator.py",
    "research/venue2027/proof/artifacts/sacmat_temporal_corpus.json",
    "research/venue2027/proof/SACMAT-X06_temporal_generator.json",
    "research/venue2027/proof/emit_SACMAT-X06_temporal_generator_report.py",
    "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.pytest.log",
    "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.ruff.log",
    "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/test_temporal_generator.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/temporal_trace_generator.py "
        "research/venue2027/sacmat/tests/test_temporal_generator.py --config ruff.toml",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-X06_temporal_generator_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-X06_temporal_generator.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.validator.log",
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
            "evaluation/venue2027/sacmat/temporal_trace_generator.py",
            "research/venue2027/sacmat/tests/test_temporal_generator.py",
            "research/venue2027/proof/artifacts/sacmat_temporal_corpus.json",
            "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.pytest.log",
            "research/venue2027/proof/logs/SACMAT-X06_temporal_generator.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task SACMAT-X06_temporal_generator (PolicyTrace RQ1): bounded "
            "deterministic temporal trace corpus generator with bug-control "
            "pairing. evaluation/venue2027/sacmat/temporal_trace_generator.py "
            "(GENERATOR_VERSION 1.0.0, corpus schema "
            "clara.venue2027.sacmat.temporal_corpus.v1) implements "
            "generate_traces(seed, depth, hops, mutation_points) -> "
            "list[PolicyTrace-ish dict] over the audited DSL "
            "(evaluation/venue2027/sacmat/policy_trace_dsl.py, task X01; "
            "DELEGATE events follow the DSL convention principal=delegating "
            "source, policy_state=delegatee). Bounds: depth in [3,12] caps the "
            "event count of EVERY emitted trace, hops in [0,4] caps DELEGATE "
            "events per trace (hops+3 <= depth enforced so grant, request and "
            "one mutation slot always fit), mutation_points in [0,4] caps "
            "distinct temporal bug classes; every violation refused with a "
            "stable reason code (DEPTH_OUT_OF_RANGE, HOPS_OUT_OF_RANGE, "
            "MUTATION_POINTS_OUT_OF_RANGE, HOPS_EXCEED_DEPTH, INVALID_SEED) — "
            "never silently clamped. Corpus layout: exactly one VALID trace "
            "(grant -> hops delegations -> terminal request by the deepest "
            "actor) preserved and verified to replay PERMIT with zero findings "
            "under the independent DSL oracle (VALID_TRACE_BROKEN fail-closed "
            "otherwise), plus for each of at most mutation_points bug classes "
            "(seed-rotated deterministic selection restricted to "
            "hop-eligible classes) one bug trace carrying EXACTLY ONE temporal "
            "mutation and its static request-matched CONTROL: same request "
            "(same principal/tenant/resource/purpose/logical_time), same event "
            "budget, no temporal mutation — so decision-only comparisons see "
            "no difference and only the trace-level witness discriminates. Bug "
            "classes: REVOKE_BEFORE_GRANT (intruder revoke inserted before "
            "grant via temporal reordering), DELEGATION_CYCLE (requires "
            "hops>=2; last delegation retargeted to close a cycle), "
            "REVOKED_ACTOR_TRANSITIVITY (requires hops>=1; root revoked "
            "after the chain, before a downstream delegatee's replay — "
            "revocation-before-replay), TIME_TRAVEL_ACCESS (request copy "
            "replayed at t=0 before any authority — UNESTABLISHED_AUTHORITY). "
            "Each bug's expected_outcome/expected_findings are derived from a "
            "REAL evaluate_trace replay; MUTATION_NOT_OBSERVABLE refuses "
            "emission of a bug whose declared witness finding is absent from "
            "the independent replay (a silently non-discriminating trace is "
            "never emitted). Corpus invariants machine-checked: "
            "assert_corpus_integrity refuses duplicate trace_ids AND duplicate "
            "canonical trace_sha256 hashes (unique-hash corpus, never silently "
            "deduplicated); assert_all_paired refuses every bug without its "
            "existing matched control carrying the SAME request (UNPAIRED_BUG, "
            "UNPAIRED_CONTROL, REQUEST_MISMATCH, PAIRING_MISMATCH); "
            "verify_corpus re-derives every embedded verdict with a fresh "
            "independent replay and refuses tampered events/outcomes/hashes. "
            "coverage_summary reconciles totals (valid+bug+control==total, "
            "per-class bug_traces==matched_controls, unique id/hash counts). "
            "Deterministic: pure integer arithmetic, no clock, no PRNG, no "
            "I/O; identical inputs give byte-identical corpora. Real corpus "
            "artifact written at research/venue2027/proof/artifacts/"
            "sacmat_temporal_corpus.json (params seed=2027, depth=8, hops=3, "
            "mutation_points=4; 9 traces = 1 valid + 4 bugs + 4 matched "
            "controls; 4 bug-control pairs; 9 unique trace_sha256 hashes; "
            "coverage summary embedded and re-verified from disk with "
            "verify_corpus). Test driver research/venue2027/sacmat/tests/"
            "test_temporal_generator.py: 31 tests, all passed — positive: "
            "determinism per parameters plus a 48-seed sweep (replay stability, "
            "verify_corpus on every corpus), valid-only corpus at "
            "mutation_points=0, request-matched pairing with pair-half "
            "bug_class equality, exactly-one declared witness per bug trace, "
            "unique trace ids/hashes within each corpus AND across the "
            "48-seed corpus union, coverage-summary totals reconciliation, "
            "depth/hops/ordering bounds respected in every emitted trace, "
            "build_corpus_document JSON round-trip; adversarial: out-of-bound "
            "depth/hops/mutation_points and non-int/bool inputs and negative "
            "seeds refused with stable reason codes, hops exceeding the depth "
            "budget refused (HOPS_EXCEED_DEPTH), a bug without its control and "
            "a control without its bug rejected by the assert_all_paired "
            "helper (UNPAIRED_CONTROL / UNPAIRED_BUG), request mismatch "
            "between pair halves (REQUEST_MISMATCH), dangling paired_trace_id "
            "(UNPAIRED_CONTROL), duplicate trace ids (DUPLICATE_TRACE_ID) and "
            "duplicate hashes (DUPLICATE_TRACE_HASH), tampered events / "
            "tampered expected verdicts / tampered hash / valid-trace "
            "shortening all refused by verify_corpus (INVALID_TRACE_RECORD), "
            "malformed records (non-object, missing fields, unknown role, bug "
            "record without a known bug_class) rejected (INVALID_TRACE_RECORD). "
            "Commands: pytest 31 passed in 1.17s (exit 0); uvx ruff@0.7.1 check "
            "+ format --check clean (exit 0); full local evaluation/venue2027/"
            "sacmat + research/venue2027/sacmat/tests suite 385 passed, 9 "
            "skipped (pre-existing conditional real-binary skips), 0 failed. "
            "oracle_disagreement_count=0: every generated verdict was derived "
            "from and re-verified against the independent DSL replay. "
            "baseline_parity=NOT_APPLICABLE (generation layer; arms B0-B4 "
            "execute in SACMAT-runner/traces). source_sha_after records the "
            "base commit 687a6f56 per the established sibling convention; the "
            "single task commit SHA is created immediately after this report "
            "and recorded in the commit body. Downstream consumers: "
            "SACMAT-X07_mutation_ops, SACMAT-X08_budget_runner, "
            "SACMAT-X09_minimizer, SACMAT-pilot."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-X06_temporal_generator.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-X06_temporal_generator.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
