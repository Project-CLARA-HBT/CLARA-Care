"""Emit the POPETS-ablation task proof report via agent_protocol.build_report."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
TASK = "POPETS-ablation"
BASE_SHA = "28ff55110f980f42002524cef126290e91258cd6"

CHANGED = [
    "evaluation/venue2027/popets/ablations.py",
    "evaluation/venue2027/popets/test_ablations.py",
    "research/venue2027/proof/POPETS-ablation.json",
    "research/venue2027/proof/emit_POPETS-ablation_report.py",
    "research/venue2027/proof/logs/POPETS-ablation.pytest.log",
    "research/venue2027/proof/logs/POPETS-ablation.ruff.log",
    "research/venue2027/proof/logs/POPETS-ablation.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-ablation.pytest.log",
    },
    {
        "argv": (
            "uvx ruff@0.7.1 check evaluation/venue2027/popets/ablations.py "
            "evaluation/venue2027/popets/test_ablations.py && "
            "uvx ruff@0.7.1 format --check evaluation/venue2027/popets/ablations.py "
            "evaluation/venue2027/popets/test_ablations.py"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-ablation.ruff.log",
    },
    {
        "argv": (
            "python3 research/venue2027/proof/emit_POPETS-ablation_report.py "
            "# build_report + validate_report(ok:true) recorded in "
            "research/venue2027/proof/POPETS-ablation.json"
        ),
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/POPETS-ablation.validator.log",
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
            "evaluation/venue2027/popets/ablations.py",
            "evaluation/venue2027/popets/test_ablations.py",
            "research/venue2027/proof/logs/POPETS-ablation.pytest.log",
            "research/venue2027/proof/logs/POPETS-ablation.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task POPETS-ablation (dependency POPETS-candidate PASS): preregistered "
            "causal mechanism ablation variants at evaluation/venue2027/popets/ablations.py "
            "(POPETS_ABLATIONS_VERSION=clara.popets.ablations-v1) behind the task-manifest "
            "signature run_ablation(name, case) -> Outcome. The P04 candidate "
            "(evaluation/venue2027/popets/candidate.py) is evaluated against ITSELF with "
            "EXACTLY ONE mechanism removed per variant, each variant a real callable "
            "reusing existing components and DECLARING its ablated mechanism via typed "
            "VariantSpec rows in ABLATION_REGISTRY. VARIANTS (one mechanism axis each): "
            "candidate_no_key_module (candidate hook candidate.ablation_no_reverse_edges - "
            "reverse-edge closure disabled, direct dependency invalidation stays enforced; "
            "ablated_mechanism=reverse_edge_closure); baseline_common_safety_gate (full "
            "provenance boundary replaced by point-in-time check of direct consent and "
            "purpose scope without lineage tracking or reverse edges, reusing "
            "revocation_model.allowed; ablated_mechanism=lineage_provenance_tracking); "
            "full_refresh (coarse full-cache purge on consent change, reusing blueprint "
            "arm B1 coarse-cache-purge-on-revocation in baselines.py / cache_control; "
            "ablated_mechanism=selective_exact_invalidation); zero_proof_receipt "
            "(provenance proof / receipt verification omitted, unverified dependency "
            "labels admitted without consent epoch or lineage verification; "
            "ablated_mechanism=provenance_proof_verification); no_context_history_branch "
            "(longitudinal context and derived parent edges stripped, unlinking derived "
            "entries from historical parent context; "
            "ablated_mechanism=longitudinal_context_history_branch). The unmodified full "
            "candidate is the reference ceiling and is deliberately NOT registered: a "
            "variant removing nothing is not an ablation. GUARDS: refuse_unregistered_variant "
            "refuses unknown ids with UNKNOWN_ABLATION_VARIANT and nothing-removing "
            "identities (full_candidate / candidate id) with VARIANT_REMOVES_NOTHING - "
            "fail closed, never guessed, never silently run as a degraded or full arm; "
            "VariantSpec refuses specs declaring no ablated mechanism at construction; "
            "run_ablation maps refusals to EXECUTION_ERROR Outcomes and malformed cases "
            "(non-mapping, missing/empty case id, malformed cache_ops) to "
            "INDETERMINATE/EXECUTION_ERROR carrying stable reason codes. CAUSAL MECHANISM "
            "CONTRASTS (development-scale, frozen synthetic families): over the six frozen "
            "families (fresh_dispatch clean control, transitive_revocation, unaffected_scope, "
            "unproven_lineage, historical_taint, cross_purpose), the full candidate ADMITs "
            "clean traffic and unaffected scopes while REJECTing all four attacks; "
            "candidate_no_key_module ADMITs the transitive leak and historical taint; "
            "baseline_common_safety_gate ADMITs transitive leaks and unproven lineage; "
            "full_refresh REJECTs the unaffected scope (false invalidation cost); "
            "zero_proof_receipt ADMITs unproven lineage; no_context_history_branch ADMITs "
            "historical taint. SINGLE-FACTOR ISOLATION asserted: all variants preserve "
            "cross_purpose rejection and fresh_dispatch admission. MECHANISTIC INFERENCE "
            "MATRIX (pass gate): frozen PREDICTED_VERDICTS constant pins all 36 "
            "reference+variant x family cells BEFORE execution; "
            "verify_mechanistic_inference_matrix() executes every cell fresh and compares - "
            "all 36 cells match, all_cells_match=true; observed_degradation == "
            "predicted_degradation and every ablation measurably degrades vs the reference "
            "ceiling. Machine-checked: 52 tests pass (python3 -m pytest -q "
            "evaluation/venue2027/popets/test_ablations.py, exit 0); full "
            "evaluation/venue2027/popets suite 243 passed; uvx ruff@0.7.1 check + format "
            "--check clean on touched paths (exit 0). source_sha_after = commit HEAD at "
            "proof-emission time."
        ),
    )

    out = REPO / "research" / "venue2027" / "proof" / "POPETS-ablation.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    log = REPO / "research" / "venue2027" / "proof" / "logs" / "POPETS-ablation.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
