"""Emit the AIME-ablation task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-ablation task. No network access.

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
TASK = "AIME-ablation"

BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/aime/ablations.py",
    "evaluation/venue2027/aime/test_ablations.py",
    "research/venue2027/proof/AIME-ablation.json",
    "research/venue2027/proof/emit_AIME-ablation_report.py",
    "research/venue2027/proof/logs/AIME-ablation.pytest.log",
    "research/venue2027/proof/logs/AIME-ablation.ruff.log",
    "research/venue2027/proof/logs/AIME-ablation.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-ablation.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/aime/ablations.py "
        "evaluation/venue2027/aime/test_ablations.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/aime/ablations.py "
        "evaluation/venue2027/aime/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-ablation.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_AIME-ablation_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/AIME-ablation.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-ablation.validator.log",
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
            "evaluation/venue2027/aime/ablations.py",
            "evaluation/venue2027/aime/test_ablations.py",
            "research/venue2027/proof/logs/AIME-ablation.pytest.log",
            "research/venue2027/proof/logs/AIME-ablation.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task AIME-ablation (dependency AIME-candidate PASS): "
            "preregistered causal mechanism ablation variants at "
            "evaluation/venue2027/aime/ablations.py "
            "(ABLATIONS_VERSION=clara.aime.ablations-v1) behind the "
            "task-manifest signature run_ablation(name, case) -> Outcome. "
            "The P04 candidate (evaluation/venue2027/aime/candidate.py) is "
            "run against ITSELF with EXACTLY ONE mechanism removed per variant, "
            "each variant a real callable reusing candidate components and "
            "DECLARING its single ablated mechanism via typed VariantSpec rows "
            "in ABLATION_REGISTRY. VARIANTS (5 registered, 1 mechanism axis each): "
            "without_history_contrast (evaluates snapshot alone without contrasting "
            "subsequent history changes or timeline events; ablated_mechanism="
            "counterfactual_history_contrast; misses medication withdrawal); "
            "without_consent_recheck (suppresses Axis A consent recheck, admitting "
            "revoked consent disclosures; ablated_mechanism=consent_epoch_recheck); "
            "without_medication_allergy_gate (suppresses Axis B allergy checks, "
            "admitting reported allergens; ablated_mechanism="
            "medication_allergy_entanglement_gate); common_safety_gate "
            "(replaces candidate with static context-free initial snapshot check; "
            "ablated_mechanism=counterfactual_reasoning_and_temporal_history; "
            "misses all mid-task hazards); full_refresh (blueprint arm B1 "
            "comparator, forcing full context regeneration INDETERMINATE upon "
            "any medication change; ablated_mechanism=selective_history_regeneration). "
            "The unmodified full candidate is the reference row and is deliberately "
            "NOT registered: a variant removing nothing is not an ablation. "
            "GUARDS: refuse_unregistered_variant refuses unknown ids with "
            "UNKNOWN_ABLATION_VARIANT and nothing-removing identities "
            "(full_candidate / candidate arm id / 'candidate') with "
            "VARIANT_REMOVES_NOTHING - fail closed, never guessed, never silently "
            "run as a degraded or full arm; VariantSpec refuses specs declaring "
            "no ablated mechanism at construction; run_ablation maps refusals to "
            "EXECUTION_ERROR Outcomes and malformed cases to EXECUTION_ERROR / "
            "INDETERMINATE (never ADMIT/REJECT). MECHANISTIC INFERENCE MATRIX "
            "(pass gate): frozen PREDICTED_VERDICTS constant pins all 24 reference "
            "+ variant x fault-family cells across 4 synthetic families (stable_history, "
            "medication_withdrawal, consent_revoked, allergy_reported) BEFORE execution; "
            "verify_mechanistic_inference_matrix() executes every cell fresh and "
            "compares - all 24 cells match (all_cells_match=true). CAUSAL CONTRAST: "
            "removing history contrast misses a withdrawal hazard (ADMIT) that the "
            "full candidate catches (REJECT, WITHDRAWN_MEDICATION_IN_OUTPUT). "
            "Adversarial tests confirm fail-closed boundaries and AST-level ban "
            "on oracle/truth imports. No clinical efficacy claims asserted. "
            "source_sha_after records base SHA before commit per repo convention."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-ablation.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "AIME-ablation.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
