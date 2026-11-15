"""Emit the ACNS-rq_registry proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced by
the ACNS-rq_registry task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "ACNS-rq_registry"
BASE_SHA = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"

CHANGED = [
    "research/venue2027/acns/rq_and_estimands.yaml",
    "research/venue2027/acns/tests/test_rq_registry.py",
    "research/venue2027/proof/ACNS-rq_registry.json",
    "research/venue2027/proof/emit_acns_rq_registry_report.py",
    "research/venue2027/proof/logs/ACNS-rq_registry.pytest.log",
    "research/venue2027/proof/logs/ACNS-rq_registry.suite.log",
    "research/venue2027/proof/logs/ACNS-rq_registry.ruff.log",
    "research/venue2027/proof/logs/ACNS-rq_registry.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/acns/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-rq_registry.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/ research/venue2027/acns/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-rq_registry.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/acns/tests/test_rq_registry.py && uvx ruff@0.7.1 format --check research/venue2027/acns/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/ACNS-rq_registry.ruff.log",
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
        artifact_paths=[
            "research/venue2027/acns/rq_and_estimands.yaml",
            "research/venue2027/acns/tests/test_rq_registry.py",
        ],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        oracle_disagreement_count=0,
        notes=(
            "P01 ACNS frozen RQ/estimand registry (task ACNS-rq_registry; deps ACNS-scope "
            "PASS + SH-analysis_policy PASS). Deliverable "
            "research/venue2027/acns/rq_and_estimands.yaml (contract "
            "clara.venue2027.acns.rq-registry.v1, YAML safe_load-verified) preregisters "
            "exactly three RQs verbatim from the blueprint, each with all required fields: "
            "research_question, independent_unit, population, estimand, paired_contrast, "
            "primary_metric, secondary_metrics, null_hypothesis, alternative_hypothesis, "
            "minimum_useful_difference, confounders, power_analysis, analysis_method, "
            "falsification_condition, primary_endpoint. SoK framing honored "
            "(estimator_frame: evidence_boundary_coverage_not_mechanism_superiority + "
            "sok_no_mechanism_clause): RQ1 endpoint = coverage of the evidence-strength "
            "lattice (residual-over-B0/B1 fraction, exact one-sided binomial H0 pi=0.05 vs "
            "H1 pi>0.15 useful difference, exact power at N=52: size 0.0445, power 0.8119); "
            "RQ2 endpoint = counterexample reproduction rate over the pre-registered G1-G9 "
            "implication-pair register (H0 rho=0.50 vs H1 rho=0.80, exact power at N=18: "
            "size 0.0481, power 0.8671; per-family exact McNemar vs B2-derived verdicts; "
            "witnesses are falsification instruments, never a defense); RQ3 endpoint = "
            "inter-rater Cohen's kappa on the pre-adjudication first-pass stream (paired "
            "bootstrap vs B3-style generic coding, registered margin 0.10, absolute floor "
            "0.60, N=120 gives CI half-width 0.0996; chance-corrected variance upper bound "
            "p0=0.775, pe=0.25). All three falsification conditions mirror "
            "novelty_contract §3 exactly (RFC 9334 suffices / reproduction below 0.80 or "
            "B0/B2 restatement / kappa margin vs B3 generic coding fail) and commit to "
            "reporting negative results with the SoK claim withdrawn. Preregistration "
            "discipline: no empirical value invented (no kappa/coverage/reproduction/"
            "corpus-size observed value asserted anywhere); all thresholds are design-time "
            "planning constants (verified by computed binomial tail sums, not rounded "
            "examples); fixed seed 20271115 for all bootstrap resampling; denominator "
            "discipline with all 8 outcome statuses; INDETERMINATE retention, never "
            "coerced; assert_frozen_analysis drift guard; oracle independence (truth.json "
            "fixed before execution, never imports witness code, no post-hoc repair). "
            "Negative/adversarial controls in tests: pseudo-replication refusal, "
            "mechanism-metric refusal (no detection/prevention/PR-AUC/replay-acceptance "
            "endpoint), invented-empirical-value refusal, placeholder refusal, oracle "
            "independence, directional hypotheses with registered bounds. Tests: 18 "
            "passed (structural + adversarial). Suite: 318 passed (shared + acns). "
            "uvx ruff@0.7.1 check + format clean on touched paths (repo-wide ruff has "
            "pre-existing unrelated findings in untouched scripts/, services/ files, per "
            "sibling convention of linting touched paths only). source_sha_after = base "
            "SHA e2836f0a per established repo convention (proof report committed together "
            "with the work; single task commit SHA created immediately after this report)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "ACNS-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
