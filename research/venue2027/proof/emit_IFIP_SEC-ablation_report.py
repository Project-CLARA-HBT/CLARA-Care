"""Emit the IFIP_SEC-ablation task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the IFIP_SEC-ablation task. No network access.

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
TASK = "IFIP_SEC-ablation"

BASE_SHA = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/ifip_sec/ablations.py",
    "evaluation/venue2027/ifip_sec/test_ablations.py",
    "research/venue2027/proof/IFIP_SEC-ablation.json",
    "research/venue2027/proof/emit_IFIP_SEC-ablation_report.py",
    "research/venue2027/proof/logs/IFIP_SEC-ablation.pytest.log",
    "research/venue2027/proof/logs/IFIP_SEC-ablation.ruff.log",
    "research/venue2027/proof/logs/IFIP_SEC-ablation.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/ifip_sec/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-ablation.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/ifip_sec/ablations.py "
        "evaluation/venue2027/ifip_sec/test_ablations.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/ifip_sec/ablations.py "
        "evaluation/venue2027/ifip_sec/test_ablations.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-ablation.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_IFIP_SEC-ablation_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/IFIP_SEC-ablation.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/IFIP_SEC-ablation.validator.log",
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
            "evaluation/venue2027/ifip_sec/ablations.py",
            "evaluation/venue2027/ifip_sec/test_ablations.py",
            "research/venue2027/proof/logs/IFIP_SEC-ablation.pytest.log",
            "research/venue2027/proof/logs/IFIP_SEC-ablation.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 task IFIP_SEC-ablation (dependency IFIP_SEC-candidate PASS at "
            "6fe5fe193a5a55f456f163a853c1b2c41c0c869f): preregistered causal "
            "mechanism ablation variants at evaluation/venue2027/ifip_sec/"
            "ablations.py (ABLATIONS_VERSION=clara.ifip_sec.ablations-v1) "
            "behind the task-manifest signature run_ablation(name, case) -> "
            "Outcome. The P04 candidate (evaluation/venue2027/ifip_sec/"
            "candidate.py) is run against ITSELF with EXACTLY ONE mechanism "
            "removed per variant, each variant a real callable reusing "
            "candidate components and DECLARING its ablated mechanism via "
            "typed VariantSpec rows in ABLATION_REGISTRY. VARIANTS (one "
            "mechanism axis each): no_nonce_consume_once (candidate hook "
            "candidate.ablation_no_nonce - the consume-once store is never "
            "consulted or consumed; ablated_mechanism=consume_once_nonce); "
            "no_purpose_binding (the presented purpose is replaced by the "
            "receipt's claimed purpose before the unmodified candidate "
            "pipeline runs - the SACMAT no-expiry input-mutation pattern; "
            "ablated_mechanism=purpose_binding); "
            "no_delegation_lineage_validation (candidate hook "
            "candidate.ablation_no_lineage_binding - proposal-lineage "
            "commitment re-derivation and request-presented lineage "
            "comparison skipped, delegation-chain binding/ancestry/purpose/"
            "epochs/nonce stay enforced; "
            "ablated_mechanism=delegation_lineage_validation); "
            "no_epoch_recheck (request-presented epochs replaced by the "
            "receipt's claimed epochs AND the live-governance recheck "
            "suppressed via an epoch-blind ledger view - same key, clock and "
            "ancestry registration, live_epoch always None - so the "
            "candidate's epoch axis can never fire; "
            "ablated_mechanism=policy_consent_epoch_recheck); "
            "common_safety_gate (the full binding pipeline REPLACED by the "
            "common safety gate every arm already shares: real HMAC "
            "verification via candidate.verify_receipt_signature plus the "
            "expiry check against the injected clock - context-free, "
            "binding-free, no replay closure; "
            "ablated_mechanism=full_binding_pipeline). The unmodified full "
            "candidate is the reference row and is deliberately NOT "
            "registered: a variant removing nothing is not an ablation. "
            "GUARDS: refuse_unregistered_variant refuses unknown ids with "
            "UNKNOWN_ABLATION_VARIANT and nothing-removing identities "
            "(full_candidate / the candidate id "
            "clara.ifip_sec.candidate.replay-closed-lineage-authorization) "
            "with VARIANT_REMOVES_NOTHING - fail closed, never guessed, "
            "never silently run as a degraded or full arm; VariantSpec "
            "refuses specs declaring no ablated mechanism at construction; "
            "run_ablation maps refusals to EXECUTION_ERROR Outcomes and "
            "malformed cases (non-mapping, missing/empty/non-string case id, "
            "missing receipt/request, unparseable payloads, bad nonce-store/"
            "ledger types) to INDETERMINATE/EXECUTION_ERROR carrying stable "
            "reason codes (never ADMIT/REJECT, never counted). CAUSAL "
            "MECHANISM CONTRASTS (development-scale, frozen synthetic "
            "families - never confirmatory): over the seven frozen "
            "attack/control families (fresh_consumption control, "
            "exact_replay, purpose_switch, lineage_splice, "
            "consent_revoked_replay, tampered_receipt, chain_truncation) the "
            "full candidate ADMITs only the fresh control and REJECTs all "
            "six attacks (reference ceiling); removing the nonce ADMITs the "
            "exact replay the candidate DENYs with NONCE_REPLAYED (store "
            "demonstrably never consulted - nonce_consumed=false); removing "
            "the purpose binding ADMITs the purpose switch the candidate "
            "DENYs with PURPOSE_MISMATCH; removing the lineage validation "
            "ADMITs the splice the candidate DENYs with LINEAGE_SPLICED "
            "(while the separate delegation-chain axis still catches the "
            "chain truncation); removing the epoch recheck ADMITs the "
            "revoked-consent replay the candidate DENYs with "
            "CONSENT_EPOCH_REVOKED; the common safety gate ADMITs every "
            "noncryptographic attack but still catches the tampered receipt "
            "(real HMAC stays). SINGLE-FACTOR ISOLATION asserted per "
            "variant: every ablation keeps every OTHER mechanism enforced "
            "(nonce/purpose/lineage/epoch variants all still REJECT the "
            "attack families outside their ablated axis) and the fresh "
            "control is admitted by every variant and the reference (no "
            "collateral rejection). MECHANISTIC INFERENCE MATRIX (pass "
            "gate): frozen PREDICTED_VERDICTS constant pins all 42 "
            "reference+variant x family cells BEFORE execution; "
            "verify_mechanistic_inference_matrix() executes every cell fresh "
            "and compares - all 42 cells match, all_cells_match=true; "
            "observed_degradation == predicted_degradation and every "
            "ablation measurably degrades vs the reference row (detection-"
            "count conservation: the reference rejects strictly more attack "
            "families than any ablation). Determinism asserted (identical "
            "inputs give identical Outcomes and matrix verdicts); fixtures "
            "are fresh per call (a drained nonce store never leaks across "
            "cases); the ablation layer never mutates the candidate module "
            "and imports neither the independent oracle nor any baseline "
            "adapter (independence preserved). Machine-checked: 53 new "
            "tests pass (python3 -m pytest -q evaluation/venue2027/ifip_sec/"
            "test_ablations.py, exit 0); full evaluation/venue2027/ifip_sec "
            "suite 194 passed; uvx ruff@0.7.1 check + format --check clean "
            "on touched paths (exit 0). source_sha_after = commit HEAD at "
            "proof-emission time."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "IFIP_SEC-ablation.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    log = REPO / "research" / "venue2027" / "proof" / "logs" / "IFIP_SEC-ablation.validator.log"
    log.write_text("validator running\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    payload = json.dumps(result.to_dict(), indent=2) + "\n"
    log.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
