"""Emit the PST-rq_registry proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the PST-rq_registry task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "PST-rq_registry"
BASE_SHA = "293bde7bce7b0a361306e40e04fba931cfc0623d"

CHANGED = [
    "research/venue2027/pst/rq_and_estimands.yaml",
    "research/venue2027/pst/tests/test_rq_registry.py",
    "research/venue2027/proof/PST-rq_registry.json",
    "research/venue2027/proof/emit_pst_rq_registry_report.py",
    "research/venue2027/proof/logs/PST-rq_registry.pytest.log",
    "research/venue2027/proof/logs/PST-rq_registry.suite.log",
    "research/venue2027/proof/logs/PST-rq_registry.ruff.log",
    "research/venue2027/proof/logs/PST-rq_registry.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q research/venue2027/pst/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-rq_registry.pytest.log",
    },
    {
        "argv": "python3 -m pytest -q research/venue2027/_shared/tests/ research/venue2027/pst/tests/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-rq_registry.suite.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check research/venue2027/pst/tests/test_rq_registry.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/PST-rq_registry.ruff.log",
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
            "research/venue2027/pst/rq_and_estimands.yaml",
            "research/venue2027/pst/tests/test_rq_registry.py",
        ],
        repo=REPO,
        unresolved=[],
        baseline_parity="NOT_APPLICABLE",
        oracle_disagreement_count=0,
        notes=(
            "P01 preregistered RQ/estimand registry for PST 2027 (task PST-rq_registry; "
            "deps PST-scope PASS + SH-analysis_policy PASS; novelty-contract Condition 1). "
            "Deliverable research/venue2027/pst/rq_and_estimands.yaml (contract "
            "clara.venue2027.rq_registry.v1, YAML safe_load-verified, "
            "preregistration_status: frozen_before_any_arm_runs) freezes exactly three RQs "
            "verbatim from the blueprint, each with all 14 required fields "
            "(research_question, independent_unit, population, estimand, paired_contrast, "
            "primary_metric, secondary_metrics, null_hypothesis, alternative_hypothesis, "
            "minimum_useful_difference, confounders, power_and_analysis_method, "
            "falsification_condition, primary_endpoint): RQ1 forensic query answerability "
            "per independent synthetic case history (B4 vs B2 two-sided paired permutation "
            "test, non-inferiority margin m1=0.05, case-family clustered, Holm across three "
            "families); RQ2 attacker advantage over declared prior per independent "
            "synthetic subject under the frozen P1+P2 compromised read-only audit reader "
            "with auxiliary joins (one-sided exact permutation test, exposure bound "
            "b2=0.10); RQ3 retained bytes / proof-generation latency / authorized recovery "
            "time per (history x volume x epoch) condition as B4-over-baseline ratios "
            "(paired case-clustered bootstrap, 10,000 resamples, seed 20271115, equivalence "
            "margin e3=0.15). Endpoint class: forensic reconstructability score — the "
            "reconstruction-versus-linkability frontier measured jointly with exposure "
            "bounds; contribution_class: measurement_not_access_control_mechanism "
            "(access_control_boundary block; B4 is an evaluation instrument, never an "
            "authorization primitive; forbidden claim patterns negation-checked). "
            "PoPETs differentiation declared (post hoc reconstruction vs future-facing "
            "re-disclosure control; PoPETs cache-invalidator never a PST baseline); frozen "
            "GLHS E15–E22 + HEALTHINF refused as new evidence (reuses_archive: []). "
            "Falsification register F1-F7 mirrors novelty_contract exactly, including the "
            "study-level B2-dominance rule. Preregistration discipline: no empirical value "
            "invented (regex-refused observed-value patterns); thresholds are design-time "
            "planning constants computed via normal-approximation power calculations "
            "(RQ1: (z0.95+z0.80)*0.20/0.05 -> N=99 histories per arm; RQ2: "
            "(z0.95+z0.80)*0.25/0.08 -> N=61 subjects; RQ3: (z0.975*0.50/0.10)^2 -> N=97 "
            "conditions), fixed seed 20271115, denominator discipline with all 8 outcome "
            "statuses, INDETERMINATE retained and never coerced, assert_frozen_analysis "
            "drift guard, oracle independence (trusted offline complete ledger held by the "
            "evaluation role, labels frozen before arms run, candidate never imports "
            "oracle code, no post-hoc repair). Tests: 24 passed (structural + adversarial "
            "controls: pseudo-replication refusal, per-event unit refusal, access-control "
            "claim refusal, sibling-endpoint refusal, invented-value refusal, placeholder "
            "refusal). Suite: 312 passed (shared + pst). uvx ruff@0.7.1 check + format "
            "clean on touched paths (repo-wide ruff has pre-existing unrelated findings in "
            "untouched files, per sibling convention of linting touched paths only). "
            "source_sha_after = base SHA 293bde7b per established repo convention (proof "
            "report committed together with the work; single task commit SHA created "
            "immediately after this report)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "PST-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
