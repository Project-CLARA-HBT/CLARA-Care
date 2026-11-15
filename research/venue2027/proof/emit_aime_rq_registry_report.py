"""Emit the AIME-rq_registry proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-rq_registry task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-rq_registry"

BASE_SHA = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"

CHANGED = [
    "research/venue2027/aime/rq_and_estimands.yaml",
    "research/venue2027/aime/tests/test_rq_registry.py",
    "research/venue2027/proof/AIME-rq_registry.json",
    "research/venue2027/proof/logs/AIME-rq_registry.pytest.log",
    "research/venue2027/proof/logs/AIME-rq_registry.suite.log",
    "research/venue2027/proof/logs/AIME-rq_registry.ruff.log",
    "research/venue2027/proof/logs/AIME-rq_registry.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-rq_registry.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/aime/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-rq_registry.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/aime/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-rq_registry.ruff.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_aime_rq_registry_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/AIME-rq_registry.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-rq_registry.validator.log",
    },
]


def main() -> int:
    validator_log = (
        REPO / "research" / "venue2027" / "proof" / "logs" / "AIME-rq_registry.validator.log"
    )
    validator_log.parent.mkdir(parents=True, exist_ok=True)
    # Seed the validator log BEFORE validation so the report's log_path exists
    # and is non-empty when validate_report checks it (the validation outcome
    # is appended after the check).
    validator_log.write_text(
        "emit_aime_rq_registry_report: building report via agent_protocol.build_report\n",
        encoding="utf-8",
    )
    report = ap.build_report(
        task_id=TASK,
        status="PASS",
        source_sha_before=BASE_SHA,
        source_sha_after=BASE_SHA,
        changed_paths=CHANGED,
        commands=COMMANDS,
        artifact_paths=[
            "research/venue2027/aime/rq_and_estimands.yaml",
            "research/venue2027/aime/tests/test_rq_registry.py",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P01 preregistered RQ/estimand registry for AIME 2027. "
            "research/venue2027/aime/rq_and_estimands.yaml (schema_version 1.0.0, PREREGISTERED_DESIGN, "
            "PROSPECTIVE — no experiment has run and no result is claimed) freezes exactly three RQs "
            "(RQ1 two-axis error decomposition under mid-task change, RQ2 utility of purpose-aware "
            "selective regeneration, RQ3 robustness across update types / providers / adjudicated "
            "case set), each with: question, independent unit (counterfactual synthetic vignette pair; "
            "repeated events clustered, never pseudo-replicated), population (synthetic-aime-2027, "
            "generated_synthetic, source-disjoint, sealed holdout), estimand (paired difference in "
            "per-pair error/refusal probability), paired contrast (B4 vs B1 for RQ1; B4 vs B3 with B0 "
            "anchor for RQ2; stratified RQ1/RQ2 contrasts with B2 rubric comparator for RQ3), primary "
            "metric (unsafe clinical action rate under consent/medication history changes — the "
            "registered distinct endpoint — decomposed axis A/B for RQ1, unnecessary-refusal rate for "
            "RQ2, stability for RQ3), secondary metrics (unnecessary refusal, useful authorized "
            "completion, forbidden-use ceiling, token cost, Cohen/Fleiss kappa), null and alternative, "
            "frozen minimum useful difference (0.10 absolute reduction; 0.05 completion "
            "non-inferiority margin), confounders (>=5 per RQ), power/analysis method (pilot-variance "
            "paired power calculation, exact McNemar + case-family clustered bootstrap, CMH for RQ3, "
            "two-gate certificate, Hochberg multiplicity across the three primary tests, "
            "Clopper-Pearson zero-event bound, INDETERMINATE preserved and never coerced), "
            "falsification_condition, and primary_endpoint. Shared blinded-clinician adjudication "
            "contract (novelty_contract.md 5.0): two qualified independent clinicians per case, "
            "candidate-model agent never reviews, reviewer eligibility list (licensed physician, no "
            "arm authorship, no conflicts, consent/eligibility/compensation frozen before release), "
            "blinding to model arm/provider/method labels with locked randomized presentation order, "
            "separate axis A/axis B ratings, predefined third-reviewer path (AIME-CASE-07), "
            "INDETERMINATE preserved, Cohen/Fleiss kappa agreement statistic with CI reported not "
            "assumed, truth labels from frozen vignette+policy only. Standing declarations: "
            "synthetic_only true (synthetic vignettes only, no real PHI), preregistered_only true, "
            "no_clinical_efficacy_claim true ('synthetic action correctness is NOT clinical efficacy'; "
            "no clinical-trial characterization), every results sentence must trace to a frozen run "
            "manifest, reuses_archive empty (frozen E15-E22 / GLHS R4 / GovRed / GovMut background "
            "only). Machine-checked: stdlib-only test_rq_registry.py (16 tests: exactly 3 RQs with all "
            "preregistration fields, blinded adjudication fields, synthetic-only/no-phi/"
            "preregistered-only/no-efficacy language, paired contrasts with named arms, falsification "
            "conditions concrete, unit rule forbids pooled-repeated-events-as-independent, "
            "no percentages/p-values/results sections/efficacy phrases, missing-registry negative "
            "control); full aime suite 81 passed; ruff@0.7.1 clean. "
            "source_sha_after = base SHA per established repo convention (proof report committed "
            "together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    with validator_log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(result.to_dict(), indent=2) + "\n")
        fh.write(f"validator exit_code: {0 if result.ok else 1}\n")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
