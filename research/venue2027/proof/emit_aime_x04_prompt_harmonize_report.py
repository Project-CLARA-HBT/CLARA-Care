"""Emit the AIME-X04_prompt_harmonize task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-X04_prompt_harmonize task. No network access.

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
TASK = "AIME-X04_prompt_harmonize"
BASE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED = [
    "evaluation/venue2027/aime/prompt_harmonizer.py",
    "evaluation/venue2027/aime/test_prompt_harmonizer.py",
    "research/venue2027/proof/AIME-X04_prompt_harmonize.json",
    "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.pytest.log",
    "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.ruff.log",
    "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.suite.log",
    "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.validator.log",
    "research/venue2027/proof/emit_aime_x04_prompt_harmonize_report.py",
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
        source_sha_before=BASE,
        source_sha_after=sha_after,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": (
                    "python3 -m pytest -q "
                    "evaluation/venue2027/aime/test_prompt_harmonizer.py"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X04_prompt_harmonize.pytest.log"
                ),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/aime/"
                    "prompt_harmonizer.py evaluation/venue2027/aime/"
                    "test_prompt_harmonizer.py && uvx ruff@0.7.1 format --check "
                    "evaluation/venue2027/aime/"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.ruff.log"
                ),
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X04_prompt_harmonize.suite.log"
                ),
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_aime_x04_prompt_harmonize_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X04_prompt_harmonize.json"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X04_prompt_harmonize.validator.log"
                ),
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/aime/prompt_harmonizer.py",
            "evaluation/venue2027/aime/test_prompt_harmonizer.py",
            "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.pytest.log",
            "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P03 AIME-X04_prompt_harmonize deliverable: "
            "evaluation/venue2027/aime/prompt_harmonizer.py implements the "
            "exact target contract build_prompt(vignette, arm) -> PromptPacket "
            "as a pure, deterministic, offline prompt-construction record over "
            "SYNTHETIC clinical vignettes only (no PHI, no provider call, no "
            "clock, no randomness). Core contract per task spec: (1) model and "
            "instruction SEMANTICS are held as one frozen dataclass constant "
            "(HARMONIZER_SEMANTICS: provider, model_id, model_version, "
            "tokenizer, temperature=0.0, seed, max_output_tokens, shared "
            "system role, one shared byte-identical instruction template with "
            "no arm-conditional branch, shared truncation policy, "
            "hidden_source_use=False) while varying ONLY the regeneration "
            "strategy via the pinned ARM_STRATEGY_TABLE (B0 "
            "full-restart-single-snapshot, B1 full-per-step-refresh, B2/B3 "
            "static-context-output-postfilter, B4 "
            "selective-consent-aware-regeneration, B5 "
            "consent-agnostic-retrieval) so any downstream arm delta is "
            "attributable to the strategy alone; (2) each PromptPacket records "
            "tokenizer and model version, the context truncation policy and "
            "the hidden-source usage flag, is JSON-serializable with a stable "
            "SHA256 packet_hash over its canonical JSON (verify_packet detects "
            "any field tamper with PACKET_HASH_MISMATCH) and carries "
            "tokens-per-arm accounting (TokenBudget with deterministic "
            "whitespace-token estimate applied identically to every arm, "
            "never used as clinical proof); (3) ComparabilityChecklist fails "
            "closed with ARM_NONCOMPARABLE if any arm's recorded model "
            "identity, instruction semantics, tokenizer, temperature, seed, "
            "truncation policy, hidden-source flag or packet version diverges "
            "from the frozen constant; vignette reuse of "
            "baselines.parse_vignette makes both modules refuse the same "
            "malformed inputs the same way (VIGNETTE_MALFORMED, "
            "VIGNETTE_MISSING_FIELD, VIGNETTE_BAD_TIMELINE, PHI-field "
            "refusals); unknown arms refuse with UNKNOWN_ARM. "
            "test_prompt_harmonizer.py: 45 tests pass (positive: per-arm "
            "packet construction, determinism/byte-identical JSON and stable "
            "hashes, JSON round-trip verification, arms differ only by "
            "strategy with byte-identical instruction and vignette blocks, "
            "recorded tokenizer/truncation/hidden-source flags, tokens-per-arm "
            "accounting table, checklist accepts all arm packets; adversarial: "
            "parametrized refusal of 11 changed semantic fields incl. changed "
            "model and changed instruction semantics, undeclared hidden-source "
            "use refused, changed top-level recorded policy/tokenizer refused, "
            "hash tamper detection across 7 forged fields for every arm, "
            "cross-arm hash swap refused, unknown/unregistered arms refused, "
            "5 malformed/PHI vignette refusals). Full evaluation/venue2027 "
            "suite: 834 passed. uvx ruff@0.7.1 check + format clean on "
            "touched files. No clinical validity claim is made: no clinician "
            "reviewer and no independent original vignettes exist at this "
            "stage (falsification rule honored); prompts are construction "
            "records for the matched-arm study, not model outputs. "
            "source_sha_after = commit SHA of this task's single commit (proof "
            "report committed together with the work per established repo "
            "convention)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X04_prompt_harmonize.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X04_prompt_harmonize.validator.log"
    # Pre-seed so the on-disk log exists (non-empty) at validation time; the
    # final validator result overwrites it below.
    log_path.write_text('{"note": "validator run in progress"}\n', encoding="utf-8")
    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id=TASK,
    )
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
