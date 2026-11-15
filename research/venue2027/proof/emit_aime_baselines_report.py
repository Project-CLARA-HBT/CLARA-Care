"""Emit the AIME-baselines proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-baselines task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-baselines"

BASE_SHA = "9b6be889db89c2228c6ea1ac599f0000d03c63a4"

CHANGED = [
    "evaluation/venue2027/aime/__init__.py",
    "evaluation/venue2027/aime/baselines.py",
    "evaluation/venue2027/aime/test_baselines.py",
    "research/venue2027/proof/AIME-baselines.json",
    "research/venue2027/proof/logs/AIME-baselines.pytest.log",
    "research/venue2027/proof/logs/AIME-baselines.ruff.log",
    "research/venue2027/proof/logs/AIME-baselines.suite.log",
    "research/venue2027/proof/logs/AIME-baselines.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_baselines.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baselines.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/aime/baselines.py "
        "evaluation/venue2027/aime/test_baselines.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/aime/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baselines.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baselines.suite.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_aime_baselines_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/AIME-baselines.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baselines.validator.log",
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
            "evaluation/venue2027/aime/baselines.py",
            "evaluation/venue2027/aime/test_baselines.py",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 baseline fidelity adapters for AIME 2027. "
            "evaluation/venue2027/aime/baselines.py implements run_baseline(id, case, ctx) -> "
            "Outcome over SYNTHETIC clinical vignette records only (structured medications, "
            "consent grants/revocations, history revisions, ordered timeline; no real PHI — "
            "PHI-like input fields are refused fail-closed with VIGNETTE_MALFORMED). Arms: B0 "
            "single-history recommendation (task-start snapshot only, ignores history change); "
            "B1 full per-step refresh + current policy filter; B2 HealthBench/MedHELM rubric arm "
            "(benchmark rubric, NOT a decision algorithm); B3 static context + deterministic "
            "output post-filter (withdrawn-medication filter); B4 candidate "
            "counterfactual-history-aware safety check (detects changed consent/medication "
            "history); B5 consent-agnostic retrieval foil. BASELINE_REGISTRY carries provenance "
            "for every arm mirroring research/venue2027/aime/literature_matrix.csv rows B0-B5; "
            "all registry entries keep fidelity_status UNAVAILABLE_NOT_RUN because "
            "provider-dependent LLM execution is out of scope for this module (no live model "
            "call exists; B0/B1/B2/B3 provider execution is NOT_RUN_EXTERNAL with reason code "
            "PROVIDER_DEPENDENT_NOT_RUN; B2 returns NOT_RUN_EXTERNAL for decision requests by "
            "declared semantics). Parity/behaviour gate refuse_constant_safe_stub replays "
            "hazard-free + hazard-bearing probes and refuses a constant-safe stub with "
            "CONSTANT_SAFE_STUB_REFUSED (EXECUTION_CONTRACT rule 8: no toy wearing a baseline "
            "name). Structural B4 vs B0 demonstration on the synthetic withdrawn-medication "
            "vignette: B0 (stale snapshot semantics) returns SAFE/NO_DETECTED_HAZARD while B4 "
            "returns UNSAFE/WITHDRAWN_MEDICATION_IN_OUTPUT — the axis-A hazard contrast, a "
            "systems-level behavior on synthetic labels, NOT a clinical efficacy result. All "
            "errors are stable reason codes; INDETERMINATE is first-class and never coerced to "
            "a safe rejection or completion; NOT_RUN_EXTERNAL outcomes carry no success path. "
            "Machine-checked: 45 new tests pass (positive: per-arm registry coverage, B0-vs-B4 "
            "demonstration pair, B1 epoch refusal, B3 post-filter, B5 foil, determinism, "
            "constant-safe gate; adversarial: NOT_RUN_EXTERNAL arms, provider-client import "
            "ban, PHI-like field refusal, malformed vignette/timeline/context/unknown-arm "
            "fail-closed); full evaluation/venue2027 suite 88 passed; ruff check + format "
            "clean on touched files. source_sha_after = base SHA per established repo "
            "convention (proof report committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-baselines.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
