"""Emit the SACMAT-rq_registry P01 task report via the shared agent protocol."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

BASE_SHA = "e2836f0a01f0fe4739d70774f3aeac1eca02baac"


def _sha(rev: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", rev],
        capture_output=True,
        check=True,
        text=True,
    ).stdout.strip()


def main() -> int:
    report = ap.build_report(
        task_id="SACMAT-rq_registry",
        status="PASS",
        source_sha_before=_sha(BASE_SHA),
        source_sha_after=_sha("HEAD"),
        changed_paths=[
            "research/venue2027/sacmat/rq_and_estimands.yaml",
            "research/venue2027/sacmat/tests/test_rq_registry.py",
            "research/venue2027/proof/SACMAT-rq_registry.json",
            "research/venue2027/proof/emit_sacmat_rq_registry_report.py",
            "research/venue2027/proof/logs/SACMAT-rq_registry.pytest.log",
            "research/venue2027/proof/logs/SACMAT-rq_registry.ruff.log",
            "research/venue2027/proof/logs/SACMAT-rq_registry.suite.log",
            "research/venue2027/proof/logs/SACMAT-rq_registry.shared_regression.log",
            "research/venue2027/proof/logs/SACMAT-rq_registry.analysis_policy.log",
        ],
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "research/venue2027/sacmat/tests/test_rq_registry.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-rq_registry.pytest.log",
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check "
                    "research/venue2027/sacmat/tests/test_rq_registry.py"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-rq_registry.ruff.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/sacmat/tests/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/SACMAT-rq_registry.suite.log",
            },
            {
                "argv": "python3 -m pytest -q research/venue2027/_shared/tests/",
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "SACMAT-rq_registry.shared_regression.log"
                ),
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/_shared/test_analysis_policy.py",
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "SACMAT-rq_registry.analysis_policy.log"
                ),
            },
        ],
        artifact_paths=[
            "research/venue2027/sacmat/rq_and_estimands.yaml",
            "research/venue2027/sacmat/tests/test_rq_registry.py",
        ],
        repo=REPO_ROOT,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P01 preregistered RQ/estimand registry for SACMAT 2027 (PolicyTrace). "
            "research/venue2027/sacmat/rq_and_estimands.yaml freezes, for each of RQ1-RQ3: "
            "research question, independent unit (delegated-consent policy case = ordered "
            "(policy history, request) pair, retries clustered, per-event pseudo-replication "
            "excluded), population (synthetic versioned policy/principal graphs, 50 "
            "independently designed mutants + reserved fresh holdout families; GovMut W8 and "
            "E15-E22 excluded), estimand, paired contrast (B4 vs B1 for RQ1; B4 vs B3 with "
            "B1/B2/B0 additional arms for RQ2; per-engine-pair parity vs static-diff competing "
            "explanation for RQ3; equal oracle-call budget everywhere), primary metric "
            "(delegation conformance divergence detection rate with per-RQ operationalization), "
            "secondary metrics, null, alternative, minimum useful difference (frozen "
            "prospectively without pilot data: 0.10/0.10/0.05 with direction), confounders, "
            "power/analysis method (exact McNemar + family-clustered bootstrap; Wilcoxon "
            "signed-rank + cluster bootstrap; Wilson intervals + exact McNemar, all at two-sided "
            "alpha 0.05 with RQ2 as Holm multiplicity primary), falsification_condition and "
            "primary_endpoint - all preregistered, zero empirical results invented "
            "(evidence_status PROSPECTIVE / NOT RUN). Upstream dependencies SACMAT-scope and "
            "SH-analysis_policy recorded PASS before signing; statistics vocabulary aligned "
            "with the frozen shared layer (evaluation/venue2027/_shared/analysis_policy.py). "
            "Machine-checked: 17 new structural tests pass (exact RQ count, all 18 mandatory "
            "fields per RQ, null-direction checks, frozen margins, >=4 confounders per RQ, "
            "B0-B4 arm coverage, multiplicity/Holdout freeze, no-results declaration); full "
            "SACMAT suite 82 passed; shared foundations regression 189 passed; frozen "
            "analysis-policy suite 25 passed; ruff clean on changed paths. Repo-wide ruff has "
            "1017 pre-existing findings at the base SHA unrelated to this task; the scoped "
            "check used by all prior SACMAT tasks is clean. Single-commit delivery on top of "
            "base e2836f0a; no worktree created or removed."
        ),
    )
    out = REPO_ROOT / "research" / "venue2027" / "proof" / "SACMAT-rq_registry.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    validation = ap.validate_report(
        json.loads(out.read_text(encoding="utf-8")),
        repo=REPO_ROOT,
        expected_task_id="SACMAT-rq_registry",
        completed_tasks=["SACMAT-scope", "SH-analysis_policy"],
        task_dependencies=["SACMAT-scope", "SH-analysis_policy"],
    )
    print(json.dumps(validation.to_dict(), indent=2))
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
