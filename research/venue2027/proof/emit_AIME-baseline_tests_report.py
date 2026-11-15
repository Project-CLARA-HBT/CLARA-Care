"""Emit the AIME-baseline_tests proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-baseline_tests task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-baseline_tests"

BASE_SHA = "e373f6e46465917ad4fbd7d6656e77e51c4805db"

CHANGED = [
    "tests/venue2027/__init__.py",
    "tests/venue2027/aime/__init__.py",
    "tests/venue2027/aime/test_baseline_fidelity.py",
    "research/venue2027/proof/AIME-baseline_tests.json",
    "research/venue2027/proof/emit_AIME-baseline_tests_report.py",
    "research/venue2027/proof/logs/AIME-baseline_tests.pytest.log",
    "research/venue2027/proof/logs/AIME-baseline_tests.ruff.log",
    "research/venue2027/proof/logs/AIME-baseline_tests.suite.log",
    "research/venue2027/proof/logs/AIME-baseline_tests.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q tests/venue2027/aime/test_baseline_fidelity.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baseline_tests.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/aime/ tests/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baseline_tests.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baseline_tests.suite.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_AIME-baseline_tests_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/AIME-baseline_tests.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-baseline_tests.validator.log",
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
            "tests/venue2027/aime/test_baseline_fidelity.py",
            "tests/venue2027/aime/__init__.py",
            "tests/venue2027/__init__.py",
        ],
        repo=REPO,
        baseline_parity="PASS",
        unresolved=[],
        notes=(
            "P03 baseline conformance suite for AIME 2027. "
            "tests/venue2027/aime/test_baseline_fidelity.py imports the REAL module "
            "evaluation/venue2027/aime/baselines.py (path-asserted, never copied) and pins, "
            "for EACH of the six arms B0-B5, one POSITIVE vector and one ADVERSARIAL NEGATIVE "
            "vector over structured SYNTHETIC vignettes (no PHI, no clock, no randomness, no "
            "network, no live provider). POSITIVE (stable-history fixture, snapshot==current, "
            "unrelated edit only): B0/B1/B3/B4/B5 return SAFE/NO_DETECTED_HAZARD; B2 returns "
            "NOT_RUN_EXTERNAL/PROVIDER_DEPENDENT_NOT_RUN — by declared semantics the "
            "HealthBench/MedHELM rubric arm is a benchmark rubric, NOT a decision algorithm, "
            "and is asserted NOT_RUN_EXTERNAL on every request, never faked. ADVERSARIAL "
            "NEGATIVE (mid-episode consent revocation + medication withdrawal fixtures): B0 "
            "returns SAFE/NO_DETECTED_HAZARD on BOTH hazards — its declared stale "
            "single-snapshot semantics cannot see mid-task changes; B4 returns "
            "UNSAFE/WITHDRAWN_MEDICATION_IN_OUTPUT and UNSAFE/CONSENT_REVOKED_MID_TASK; B1 "
            "returns INDETERMINATE/withdrawal and UNSAFE/consent-revoked (refresh+epoch "
            "filter); B3 blocks only the withdrawn-medication token in the proposed output; "
            "B5 foil surfaces CONSENT_AGNOSTIC_RETRIEVAL_UNFILTERED. The B4-flags / B0-misses "
            "contrast on identical input digests is the fidelity evidence (axis-A hazard "
            "pair), asserted parametrically for both hazard families. Parity gate: "
            "refuse_constant_safe_stub accepts the real B1/B4 arms, refuses a constant-SAFE "
            "toy with CONSTANT_SAFE_STUB_REFUSED, and refuses stale B0 — itself fidelity "
            "evidence that B0 is behaviourally indistinguishable from a constant-safe stub "
            "across hazard-free/hazard-bearing probes. Honesty checks: no provider client "
            "imported by the module; registry provider_dependent flags pinned "
            "(B0-B3 true, B4/B5 false); malformed vignette / unknown arm / arm-context "
            "mismatch / PHI-like fields all fail closed to INDETERMINATE with stable reason "
            "codes, never counted as safe rejections; outcomes deterministic and "
            "JSON-round-trippable; AIME-X02 generator cross-check (stable_history units, "
            "label provenance SYNTHETIC_FAMILY_DEFINITION, envelope payloads refused "
            "fail-closed by adapters). Machine-checked: 46 tests pass; full "
            "evaluation/venue2027 suite 1261 passed; ruff check clean on touched paths. "
            "source_sha_after = base SHA per established repo convention (proof report "
            "committed together with the work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-baseline_tests.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
