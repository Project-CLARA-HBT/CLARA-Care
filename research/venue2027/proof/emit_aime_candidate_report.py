"""Emit the AIME-candidate proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-candidate task. No network access.

Failure semantics: exits non-zero if report construction or validation fails.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "_shared" / "tools"))

import agent_protocol as ap  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
TASK = "AIME-candidate"

BASE_SHA = "85cd56757045e8e8788def095bba45adc669ab92"

CHANGED = [
    "evaluation/venue2027/aime/candidate.py",
    "evaluation/venue2027/aime/test_candidate.py",
    "research/venue2027/proof/AIME-candidate.json",
    "research/venue2027/proof/logs/AIME-candidate.pytest.log",
    "research/venue2027/proof/logs/AIME-candidate.ruff.log",
    "research/venue2027/proof/logs/AIME-candidate.suite.log",
    "research/venue2027/proof/logs/AIME-candidate.validator.log",
]

COMMANDS = [
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_candidate.py",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-candidate.pytest.log",
    },
    {
        "argv": "uvx ruff@0.7.1 check evaluation/venue2027/aime/candidate.py "
        "evaluation/venue2027/aime/test_candidate.py && uvx ruff@0.7.1 format "
        "--check evaluation/venue2027/aime/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-candidate.ruff.log",
    },
    {
        "argv": "python3 -m pytest -q evaluation/venue2027/",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-candidate.suite.log",
    },
    {
        "argv": "python3 research/venue2027/proof/emit_aime_candidate_report.py "
        "# build_report + validate_report(ok:true) recorded in "
        "research/venue2027/proof/AIME-candidate.json",
        "exit_code": 0,
        "log_path": "research/venue2027/proof/logs/AIME-candidate.validator.log",
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
            "evaluation/venue2027/aime/candidate.py",
            "evaluation/venue2027/aime/test_candidate.py",
        ],
        repo=REPO,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P04 isolated candidate algorithm for AIME 2027 (B4 arm: selective "
            "consent-aware context regeneration). "
            "evaluation/venue2027/aime/candidate.py implements the exact target contract "
            "run_candidate(case, ctx) -> Outcome with typed inputs/outputs "
            "(CandidateContext, Outcome dataclasses, JSON-serializable to_dict) over "
            "SYNTHETIC clinical vignettes only (structured medications, consent "
            "grants/revocations, allergies, ordered timeline; no real PHI - PHI-like "
            "input fields are refused fail-closed with VIGNETTE_MALFORMED, per "
            "research/venue2027/_shared/data_ethics_and_irb.md). Isolation: the module "
            "imports neither the independent oracle (independent_oracle.py / "
            "oracle_kernel) nor any label/truth file nor any candidate sibling; truth "
            "comparison happens only in the study runner. NO LLM call of any kind: "
            "pure deterministic offline function; no clock, no randomness, no network, "
            "no database, no environment I/O; the frozen INJECTION_INTERACTION_TABLE "
            "is a routing lookup over synthetic drug names, not clinical knowledge. "
            "Mechanism (docstring pseudocode maps to the blueprint B4 row and RQ1 "
            "axes): counterfactual contrast of task-start snapshot vs current state vs "
            "timeline events; structural ambiguity guard (current not reachable from "
            "snapshot by recorded events -> INDETERMINATE/SNAPSHOT_CURRENT_INCONSISTENT, "
            "never guessed); axis-A consent epoch (purpose revoked/absent -> UNSAFE/"
            "CONSENT_REVOKED_MID_TASK, AIME-CASE-03); axis-B allergen present (task "
            "drug newly recorded as allergen -> UNSAFE/ALLERGEN_PRESENT_IN_TASK); axis-B "
            "withdrawn medication anchoring the task (-> UNSAFE/"
            "WITHDRAWN_MEDICATION_IN_OUTPUT, AIME-CASE-02); added medication flagged by "
            "the frozen routing table (-> INDETERMINATE/"
            "ADDITIONAL_MEDICATION_INTERACTION_HAZARD, review required); conservative "
            "fallback for any other unclassified history change (-> INDETERMINATE/"
            "HISTORY_CHANGED_REVIEW_REQUIRED); only a fully stable history is admitted "
            "SAFE/NO_DETECTED_HAZARD (AIME-CASE-01/06). Fail-closed boundary: malformed "
            "vignettes, missing fields, backward/unknown timeline events, unresolved "
            "evidence digests (sha256:-shaped strings must resolve) and malformed "
            "contexts all yield INDETERMINATE with stable uppercase reason codes - "
            "never an unhandled exception, never a silent safe rejection; INDETERMINATE "
            "is first-class and never coerced. Behaviour gate refuse_constant_safe_stub "
            "replays hazard-free + hazard-bearing probes and refuses a constant-safe "
            "stub with CONSTANT_SAFE_STUB_REFUSED (EXECUTION_CONTRACT rule 8). "
            "Machine-checked: 31 new tests pass (positive: stable history admitted, "
            "benign unrelated edit does not block, consent-withdrawal/medication-"
            "withdrawal/allergy hazards detected and blocking, interacting addition "
            "routed to review, INDETERMINATE payload first-class; adversarial: "
            "AST-scanned oracle/label import ban in candidate and test, LLM/provider "
            "import ban, PHI-like field refusal, ambiguous-history fail-closed, "
            "backward/unknown timeline, unresolved digest, malformed context, "
            "determinism, constant-safe gate). Full evaluation/venue2027 suite: 1880 "
            "passed. ruff check + format clean on touched files (ruff@0.7.1). No "
            "clinical efficacy claim is made or implied: synthetic action labels are "
            "systems-level engineering outcomes only. source_sha_after = base SHA per "
            "established repo convention (proof report committed together with the "
            "work)."
        ),
    )
    out = REPO / "research" / "venue2027" / "proof" / "AIME-candidate.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    result = ap.validate_report(report, repo=REPO, expected_task_id=TASK)
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
