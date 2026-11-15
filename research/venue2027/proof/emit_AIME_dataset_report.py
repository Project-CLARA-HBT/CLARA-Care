"""Emit research/venue2027/proof/AIME-dataset.json via agent_protocol.build_report.

Builds the task report for the AIME-dataset deliverable with real log paths
captured during verification, then validates it with
``agent_protocol.validate_report`` and records the validator result in
``research/venue2027/proof/logs/AIME-dataset.validator.log``.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "06125d5291c6aa4b1d65df6df1d0d7e56de58463"

CHANGED = [
    "evaluation/venue2027/aime/generate_dataset.py",
    "evaluation/venue2027/aime/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/aime_dataset/dataset.jsonl",
    "research/venue2027/proof/artifacts/aime_dataset/inventory.json",
    "research/venue2027/proof/artifacts/aime_dataset/manifest.json",
    "research/venue2027/proof/logs/AIME-dataset.pytest.log",
    "research/venue2027/proof/logs/AIME-dataset.ruff.log",
    "research/venue2027/proof/logs/AIME-dataset.suite.log",
    "research/venue2027/proof/logs/AIME-dataset.artifact.log",
    "research/venue2027/proof/logs/AIME-dataset.validator.log",
    "research/venue2027/proof/emit_AIME_dataset_report.py",
    "research/venue2027/proof/AIME-dataset.json",
]


def main() -> int:
    report = ap.build_report(
        task_id="AIME-dataset",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/aime/test_generate_dataset.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-dataset.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/aime/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-dataset.ruff.log",
            },
            {
                "argv": (
                    "python3 -m evaluation.venue2027.aime.generate_dataset "
                    "--outdir research/venue2027/proof/artifacts/aime_dataset "
                    "--seed 2027 --n 200"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-dataset.artifact.log",
            },
            {
                "argv": (
                    "python3 -m pytest -q evaluation/venue2027/ "
                    "research/venue2027/_shared/tests/ research/venue2027/aime/tests/"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/AIME-dataset.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/aime/generate_dataset.py",
            "evaluation/venue2027/aime/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/aime_dataset/dataset.jsonl",
            "research/venue2027/proof/artifacts/aime_dataset/inventory.json",
            "research/venue2027/proof/artifacts/aime_dataset/manifest.json",
            "research/venue2027/proof/logs/AIME-dataset.pytest.log",
            "research/venue2027/proof/logs/AIME-dataset.ruff.log",
            "research/venue2027/proof/logs/AIME-dataset.suite.log",
            "research/venue2027/proof/logs/AIME-dataset.artifact.log",
        ],
        repo=REPO,
        oracle_disagreement_count=None,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "AIME-dataset (P02, venue aime): deterministic synthetic dataset and split builder "
            "for 'Counterfactual Clinical Workflow Safety under Changing Consent and Medication "
            "Histories'. evaluation/venue2027/aime/generate_dataset.py implements the manifest "
            "signature generate(seed, split, n) -> Dataset plus write_dataset(outdir, seed, n) "
            "by delegating record construction, family assignment, split-by-independent-unit, "
            "content hashing and the fail-closed validators (detect_split_leakage / "
            "assert_no_leakage / assert_valid_frequencies / PHI-field rejection) entirely to the "
            "audited shared kernel evaluation.venue2027._shared.dataset_kernel (v1.0.0, kernel "
            "venue families stable_history / consent_change / medication_withdrawal / "
            "allergy_update / reconciliation; unit prefix vig; 60/20/20 split; split-independent "
            "buffered content hash); nothing is re-implemented locally. This module adds only "
            "the AIME-specific longitudinal workflow payload clara.aime.workflow-payload-v1 "
            "(synthetic medication state incl. withdrawn medication, allergy state, consent "
            "revision 1-3 with revoked purpose for consent_change, conflicting observation "
            "sources for reconciliation, logical_time, update_family + CASE_MATRIX event_kind), "
            "derived by pure integer arithmetic from (seed, family, idx) - no RNG object, no "
            "clock, no dict iteration order, no live provider. Fail-closed semantics: kernel "
            "reason codes UNKNOWN_VENUE/INVALID_N/UNKNOWN_SPLIT/SPLIT_LEAKAGE/"
            "INVALID_FAMILY_FREQUENCY/EMPTY_DATASET/PHI_FIELD_PRESENT plus local "
            "UNKNOWN_AIME_FAMILY for unregistered workflow families; write_dataset runs "
            "validate_dataset (assert_valid_frequencies + assert_no_leakage via per-split "
            "regeneration) BEFORE any file is written. Real dataset artifact committed at "
            "research/venue2027/proof/artifacts/aime_dataset/ (seed=2027, n=200; content_sha256 "
            "2ff1c736947dfa90c77593b18e2ae321401dc437ce23430a87621ef4585b1fcb; jsonl_sha256 "
            "f8cf234c72597a78611ae387d987fb3594fcbaf659b1cd8915d4b58dab39c823; by_split "
            "120/40/40, by_family 5x40; dataset.jsonl + inventory.json + manifest.json; guards "
            "re-verified on the artifact). Tests 14 passed: positive (same-seed identical "
            "content hash and byte-identical JSONL incl. write_dataset reruns, seed "
            "sensitivity, split filter returns exactly that split with hash/inventory "
            "split-independence, inventory totals==n across records/splits/families/written "
            "artifacts, no leakage across the three split views, balanced family frequencies "
            "within kernel tolerance 0.35, kernel vig- unit-id prefix and uniqueness, workflow "
            "payload present/deterministic/family-shaped with consent revisions sweeping "
            "{1,2,3}, bundled validate_dataset accepts healthy output) and adversarial (same "
            "unit_id in two splits detected SPLIT_LEAKAGE by the kernel; zero-record and "
            "dominant families refused INVALID_FAMILY_FREQUENCY; unknown split 'holdout' "
            "refused UNKNOWN_SPLIT; unknown family refused UNKNOWN_AIME_FAMILY; n<=0 refused "
            "INVALID_N; no PHI-named field in any payload or written artifact plus structural "
            "placeholder value checks). baseline_parity=NOT_APPLICABLE: dataset builder, no "
            "baseline arms involved. Regression: full evaluation/venue2027/ + "
            "research/venue2027/_shared/tests/ + research/venue2027/aime/tests/ = 933 passed. "
            "uvx ruff@0.7.1 check clean on evaluation/venue2027/aime/. source_sha_after = base "
            "SHA 06125d52 per sibling dataset-task convention: the single task commit is "
            "created immediately after this report and recorded in the commit body."
        ),
    )

    # Proof file lives at research/venue2027/proof/AIME-dataset.json.
    out_path = REPO / "research/venue2027/proof/AIME-dataset.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="AIME-dataset",
        completed_tasks=["AIME-schema", "SH-schedule_engine"],
        task_dependencies=["AIME-schema", "SH-schedule_engine"],
    )
    log_path = REPO / "research/venue2027/proof/logs/AIME-dataset.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
