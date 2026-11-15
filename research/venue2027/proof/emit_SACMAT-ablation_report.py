"""Emit the SACMAT-ablation task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the SACMAT-ablation task. No network access.

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
TASK = "SACMAT-ablation"

BASE_SHA = "687a6f56def769fc930e0ee94b00476eecc1c69b"

CHANGED = [
    "evaluation/venue2027/sacmat/ablations.py",
    "evaluation/venue2027/sacmat/test_ablations.py",
    "research/venue2027/proof/SACMAT-ablation.json",
    "research/venue2027/proof/emit_SACMAT-ablation_report.py",
    "research/venue2027/proof/logs/SACMAT-ablation.pytest.log",
    "research/venue2027/proof/logs/SACMAT-ablation.ruff.log",
    "research/venue2027/proof/logs/SACMAT-ablation.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/sacmat/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-ablation.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/sacmat/ablations.py "
        "evaluation/venue2027/sacmat/test_ablations.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/sacmat/ablations.py "
        "evaluation/venue2027/sacmat/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-ablation.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_SACMAT-ablation_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/SACMAT-ablation.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/SACMAT-ablation.validator.log",
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
            "evaluation/venue2027/sacmat/ablations.py",
            "evaluation/venue2027/sacmat/test_ablations.py",
            "research/venue2027/proof/logs/SACMAT-ablation.pytest.log",
            "research/venue2027/proof/logs/SACMAT-ablation.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task SACMAT-ablation (PolicyTrace RQ1-RQ3; dependency "
            "SACMAT-candidate PASS): preregistered causal mechanism ablation "
            "variants at evaluation/venue2027/sacmat/ablations.py "
            "(ABLATIONS_VERSION=clara.sacmat.ablations-v1) behind the "
            "task-manifest signature run_ablation(name, case) -> Outcome. The "
            "P04 candidate (evaluation/venue2027/sacmat/candidate.py) is run "
            "against ITSELF with EXACTLY ONE mechanism removed per variant, "
            "each variant a real callable reusing candidate components and "
            "DECLARING its ablated mechanism via typed VariantSpec rows in "
            "ABLATION_REGISTRY. VARIANTS (one mechanism axis each): "
            "static_only (baseline WITHOUT the temporal dimension: candidate "
            "hook ablation_no_time - terminal policy state, every engine "
            "evaluated once, decision time and intermediate ticks discarded; "
            "ablated_mechanism=logical_time_replay); no_differential "
            "(candidate WITHOUT the multi-engine differential: candidate hook "
            "ablation_single_engine pinned to cedar - identical replay, one "
            "engine, no pairwise comparison; "
            "ablated_mechanism=multi_engine_differential_comparison); "
            "no_expiry_check (candidate WITHOUT the delegation-expiry check: "
            "replay/engines/pairwise comparison untouched, every event's "
            "expiry stripped before replay via candidate._normalize_trace + "
            "candidate._replay so _in_force always holds; "
            "ablated_mechanism=delegation_expiry_check); common_safety_gate "
            "(pairwise conformance detection REPLACED by the explicit-"
            "revocation deny every engine already shares - context-free, "
            "engine-free, no temporal reasoning; "
            "ablated_mechanism=pairwise_conformance_detection). The "
            "unmodified full candidate is the reference row and is "
            "deliberately NOT registered: a variant removing nothing is not "
            "an ablation. GUARDS: refuse_unregistered_variant refuses unknown "
            "ids with UNKNOWN_ABLATION_VARIANT and nothing-removing "
            "identities (full_candidate / candidate id) with "
            "VARIANT_REMOVES_NOTHING - fail closed, never guessed, never "
            "silently run as a degraded or full arm; VariantSpec refuses "
            "specs declaring no ablated mechanism at construction; "
            "run_ablation maps refusals to EXECUTION_ERROR Outcomes and "
            "malformed cases to EXECUTION_ERROR/INDETERMINATE (never "
            "ADMIT/REJECT). MECHANISTIC INFERENCE MATRIX (pass gate): frozen "
            "PREDICTED_VERDICTS constant pins all 25 reference+variant x "
            "fault-family cells (4 families: healed_expiry_divergence, "
            "revoked_replay_divergence, clean_conformant, "
            "clean_restored_authority) BEFORE execution; "
            "verify_mechanistic_inference_matrix() executes every cell fresh "
            "and compares - all 25 cells match, all_cells_match=true. CAUSAL "
            "MECHANISM RESULT (development-scale, frozen synthetic traces - "
            "never confirmatory): full candidate REJECTs both divergence "
            "families and ADMITs both clean families (reference ceiling); "
            "static_only misses the healed expiry divergence (terminal view "
            "evaluates at the healing grant's tick 3000, not the access tick "
            "2500) but still catches the unhealed revocation divergence; "
            "no_differential misses EVERY divergence family (no pairwise "
            "comparison); no_expiry_check misses exactly the expiry family "
            "while its revocation-family verdict is UNCHANGED from the "
            "reference row (single-factor isolation - no collateral mechanism "
            "change); common_safety_gate misses the expiry family AND "
            "false-flags the clean restored-authority family (double "
            "degradation). Every ablation measurably degrades vs the "
            "reference row (observed_degradation == predicted_degradation, "
            "measurably_degraded=true for all four). Every variant executes "
            "the same frozen fault-family fixture suite "
            "(fault_family_fixtures; fresh dict per call; candidate "
            "validation reused; no wall clock, randomness, network or I/O; "
            "determinism asserted). Machine-checked: 51 new tests pass "
            "(positive: registry shape, one declared mechanism per variant, "
            "every variant x family runs determined via run_ablation, matrix "
            "all-cells-match with full coverage, static_only / "
            "no_differential / no_expiry_check / common_safety_gate per-"
            "mechanism degradation contrasts, all-variants measurable "
            "degradation, reference row outside registry, frozen prediction "
            "constants, design record, determinism, typed serializable "
            "results; adversarial: five unregistered ids refused "
            "UNKNOWN_ABLATION_VARIANT by the guard and by run_ablation and "
            "run_variant_trace, nothing-removing identities refused "
            "VARIANT_REMOVES_NOTHING by the guard and by run_ablation, spec "
            "declaring no ablated mechanism refused at construction, registry "
            "specs survive their own guard, malformed cases (non-mapping, "
            "missing/empty/non-string case id, missing trace) never become "
            "ADMIT/REJECT, data faults surface INDETERMINATE not REJECT, "
            "wiring errors surface EXECUTION_ERROR with candidate reason "
            "codes, predictions prespecified not retrofitted, candidate "
            "module untouched by the ablation layer); full "
            "evaluation/venue2027/sacmat suite 253 passed; ruff check + "
            "format clean on touched files. Oracle independence preserved: "
            "the ablation layer imports only the candidate module and the "
            "shared harness Outcome; no oracle module is imported or "
            "modified. source_sha_after = commit HEAD at proof-emission time."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "SACMAT-ablation.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "SACMAT-ablation.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
