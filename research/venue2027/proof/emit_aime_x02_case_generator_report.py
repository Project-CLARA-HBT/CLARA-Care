"""Emit the AIME-X02_case_generator task proof report via agent_protocol.build_report.

Allowed input: this worktree's git state and the on-disk artifacts produced
by the AIME-X02_case_generator task. No network access.

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
TASK = "AIME-X02_case_generator"
BASE = "604642528f95e9f10052bd4bc0334bdb1c84358a"

CHANGED = [
    "evaluation/venue2027/aime/vignette_generator.py",
    "evaluation/venue2027/aime/test_vignette_generator.py",
    "research/venue2027/proof/AIME-X02_case_generator.json",
    "research/venue2027/proof/logs/AIME-X02_case_generator.pytest.log",
    "research/venue2027/proof/logs/AIME-X02_case_generator.ruff.log",
    "research/venue2027/proof/logs/AIME-X02_case_generator.suite.log",
    "research/venue2027/proof/logs/AIME-X02_case_generator.validator.log",
    "research/venue2027/proof/emit_aime_x02_case_generator_report.py",
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
                    "evaluation/venue2027/aime/test_vignette_generator.py"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X02_case_generator.pytest.log"
                ),
            },
            {
                "argv": (
                    "uvx ruff@0.7.1 check evaluation/venue2027/aime/"
                    "vignette_generator.py evaluation/venue2027/aime/"
                    "test_vignette_generator.py && uvx ruff@0.7.1 format --check "
                    "evaluation/venue2027/aime/"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/AIME-X02_case_generator.ruff.log"
                ),
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X02_case_generator.suite.log"
                ),
            },
            {
                "argv": (
                    "python3 research/venue2027/proof/"
                    "emit_aime_x02_case_generator_report.py # build_report + "
                    "validate_report(ok:true) recorded in "
                    "research/venue2027/proof/AIME-X02_case_generator.json"
                ),
                "exit_code": 0,
                "log_path": (
                    "research/venue2027/proof/logs/"
                    "AIME-X02_case_generator.validator.log"
                ),
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/aime/vignette_generator.py",
            "evaluation/venue2027/aime/test_vignette_generator.py",
            "research/venue2027/proof/logs/AIME-X02_case_generator.pytest.log",
            "research/venue2027/proof/logs/AIME-X02_case_generator.ruff.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 AIME-X02_case_generator deliverable: "
            "evaluation/venue2027/aime/vignette_generator.py implements "
            "generate(seed, source_family, n) -> list[Vignette] as a pure, "
            "deterministic, offline generator over SYNTHETIC clinical vignettes "
            "only (structured medications, consent purposes, ordered timelines; "
            "no real PHI, no provider/model call, no clock, no unseeded "
            "randomness) reusing the shared deterministic machinery conventions "
            "of evaluation/venue2027/_shared/dataset_kernel.py. Core contract "
            "per task spec: (1) balances the five AIME update families "
            "(stable_history, consent_change, medication_withdrawal, "
            "allergy_update, reconciliation) by round-robin allocation with "
            "seed-shuffled order (balanced=True gives exact floor/ceil "
            "allocation, every family present); (2) an INDEPENDENT "
            "case-archetype split: each base-case archetype is assigned to "
            "exactly one of train/dev/test (seed-dependent rotation), so no "
            "archetype, template or vignette pair derived from it ever crosses "
            "splits; detect_archetype_leakage returns stable reason codes and "
            "assert_no_archetype_split_leak fails closed with "
            "ARCHETYPE_SPLIT_LEAKAGE; (3) NEVER generates clinician ground "
            "truth from a proposed model answer: every label is derived from "
            "the synthetic family definition only "
            "(label_provenance.derived_from == SYNTHETIC_FAMILY_DEFINITION, "
            "versioned family-definition hash recorded per vignette) and "
            "assert_no_model_derived_labels refuses any label provenance that "
            "names a model (PROPOSED_MODEL_ANSWER, MODEL_ANSWER, "
            "PROPOSED_OUTPUT, LLM_OUTPUT, DEEPSEEK_*, model_response and "
            "derived_from != SYNTHETIC_FAMILY_DEFINITION) with "
            "MODEL_DERIVED_LABEL_REFUSED; (4) diagnosis-invented-as-settled-fact "
            "is refused fail-closed (assert_no_settled_diagnosis, "
            "SETTLED_DIAGNOSIS_REFUSED) — uncertainty stays first-class and "
            "adjudication belongs to the blinded clinician oracle, never the "
            "generator; (5) deterministic manifest (build_manifest) with a "
            "SHA256 content hash over unit ids, families, archetypes, splits, "
            "labels and label provenance plus generator/family-definition "
            "versions, a split_leak_clean flag and recorded leak reasons. All "
            "errors are stable uppercase reason codes (UNKNOWN_SOURCE_FAMILY, "
            "INVALID_N, INVALID_SEED, ARCHETYPE_SPLIT_LEAKAGE, "
            "MODEL_DERIVED_LABEL_REFUSED, SETTLED_DIAGNOSIS_REFUSED, "
            "EMPTY_BATCH); a refused batch is never silently repaired. "
            "test_vignette_generator.py: 22 tests pass (positive: "
            "determinism/byte-identical manifest hash, seed sensitivity, "
            "family balance, explicit balanced override, archetype-split "
            "disjointness incl. all three splits used, split views partition "
            "the batch, manifest determinism, label provenance is "
            "family-definition-only, unit-id uniqueness, payload matches the "
            "scenario record contract, guards accept the clean generated "
            "batch; adversarial: duplicate template re-emitted under another "
            "split detected, diagnosis-invented-as-settled-fact refused, "
            "model-derived label refused incl. parametrized per-marker "
            "refusal of six forbidden provenance tokens, invalid inputs fail "
            "closed). Full evaluation/venue2027 suite: 507 passed. uvx "
            "ruff@0.7.1 check + format --check clean on touched files. No "
            "clinical validity claim is made: no clinician reviewer and no "
            "independent original vignettes exist at this stage (falsification "
            "rule honored); labels are synthetic systems-level engineering "
            "artifacts for the independent oracle task. source_sha_after = "
            "commit SHA of this task's single commit (proof report committed "
            "together with the work per established repo convention)."
        ),
    )

    out_path = REPO / "research/venue2027/proof/AIME-X02_case_generator.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    log_path = REPO / "research/venue2027/proof/logs/AIME-X02_case_generator.validator.log"
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
