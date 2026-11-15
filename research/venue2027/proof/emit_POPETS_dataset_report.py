"""Emit research/venue2027/proof/POPETS-dataset.json via agent_protocol.build_report.

Builds the task report for the POPETS-dataset deliverable with real log paths
captured during verification, then validates it with
``agent_protocol.validate_report`` and records the validator result in
``research/venue2027/proof/logs/POPETS-dataset.validator.log``.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "e5f7ee3b32c6463f8bdf7c30a1e3bf987ca15bb2"

CHANGED = [
    "evaluation/venue2027/popets/generate_dataset.py",
    "evaluation/venue2027/popets/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/popets_dataset/manifest.json",
    "research/venue2027/proof/artifacts/popets_dataset/inventory.json",
    "research/venue2027/proof/artifacts/popets_dataset/dataset.jsonl",
    "research/venue2027/proof/logs/POPETS-dataset.pytest.log",
    "research/venue2027/proof/logs/POPETS-dataset.ruff.log",
    "research/venue2027/proof/logs/POPETS-dataset.suite.log",
    "research/venue2027/proof/logs/POPETS-dataset.artifact.log",
    "research/venue2027/proof/logs/POPETS-dataset.validator.log",
    "research/venue2027/proof/emit_POPETS_dataset_report.py",
    "research/venue2027/proof/POPETS-dataset.json",
]


def main() -> int:
    report = ap.build_report(
        task_id="POPETS-dataset",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/popets/test_generate_dataset.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-dataset.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/popets/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-dataset.ruff.log",
            },
            {
                "argv": (
                    "python3 -m evaluation.venue2027.popets.generate_dataset "
                    "--outdir research/venue2027/proof/artifacts/popets_dataset "
                    "--seed 2027 --n 200"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-dataset.artifact.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/POPETS-dataset.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/popets/generate_dataset.py",
            "evaluation/venue2027/popets/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/popets_dataset/manifest.json",
            "research/venue2027/proof/artifacts/popets_dataset/inventory.json",
            "research/venue2027/proof/artifacts/popets_dataset/dataset.jsonl",
            "research/venue2027/proof/logs/POPETS-dataset.pytest.log",
            "research/venue2027/proof/logs/POPETS-dataset.ruff.log",
            "research/venue2027/proof/logs/POPETS-dataset.suite.log",
            "research/venue2027/proof/logs/POPETS-dataset.artifact.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "POPETS-dataset (P02, venue popets): deterministic synthetic dataset and split "
            "builder for 'Revocation-Complete Future Disclosure for Cached Longitudinal AI "
            "Contexts'. evaluation/venue2027/popets/generate_dataset.py implements the "
            "manifest signature generate(seed, split, n) -> Dataset plus "
            "write_dataset(outdir, seed, n) by delegating record construction, family "
            "assignment, split-by-independent-unit, content hashing and the fail-closed "
            "validators (detect_split_leakage / assert_no_leakage / "
            "assert_valid_frequencies / PHI-field rejection) entirely to the audited shared "
            "kernel evaluation.venue2027._shared.dataset_kernel (v1.0.0 pinned; kernel venue "
            "families fresh / revoked_then_dispatch / cross_purpose / transitive_gap; unit "
            "prefix rev; 60/20/20 split; split-independent buffered content hash); nothing "
            "is re-implemented locally. This module adds only the POPETS-specific "
            "revocation-and-dispatch payload clara.popets.revocation-payload-v1 "
            "(revocation instant revocation_at=100 with dispatch_at in [101,400] so every "
            "record encodes a post-revocation dispatch decision; purpose over the CASE_MATRIX "
            "vocabulary self_care/care_summary/medication_review with cross_purpose records "
            "forced onto a genuinely different requested_purpose (POPETS-CASE-05 confusion); "
            "cache_mode over none/prompt_only/summary_pointer/retry_payload with 'none' "
            "reserved for fresh dispatches (RQ3 cache-hit accounting); lineage_paths over the "
            "blueprint derivation paths prompt_segment/cached_summary/embedding_pointer/"
            "retry_payload/fallback_transport with lineage_gap=True marking the "
            "transitive_gap family (POPETS-CASE-03/07 missing ancestry); "
            "subject_history_length in [3,6] per the blueprint's 3-6 longitudinal contexts "
            "per synthetic subject), derived by pure integer arithmetic from "
            "(seed, family, idx) - no RNG object, no clock, no dict iteration order, no live "
            "provider. Fail-closed semantics: kernel reason codes UNKNOWN_VENUE/INVALID_N/"
            "UNKNOWN_SPLIT/SPLIT_LEAKAGE/INVALID_FAMILY_FREQUENCY/EMPTY_DATASET/"
            "PHI_FIELD_PRESENT plus local UNKNOWN_POPETS_FAMILY for unregistered payload "
            "families; write_dataset runs validate_dataset (assert_valid_frequencies + "
            "assert_no_leakage via per-split regeneration) BEFORE any file is written. Real "
            "dataset artifact committed at research/venue2027/proof/artifacts/popets_dataset/ "
            "(seed=2027, n=200; content_sha256 "
            "9af9aaaae33cf71caa88fa4cea9c36659015743f13ec0da4fbb4925d6ede5b67; jsonl_sha256 "
            "49dcb5b9eb354f6182f5a4af287cf0a163982806e71bcb5d81daf9e0454b81e3; by_split "
            "120/40/40, by_family 4x50; dataset.jsonl + inventory.json + manifest.json; "
            "synthetic_only=true, phi_fields=[]). Tests 14 passed: positive (same-seed "
            "identical content hash and byte-identical JSONL incl. write_dataset reruns, "
            "seed sensitivity, split filter returns exactly that split with hash/inventory "
            "split-independence, inventory totals==n across records/splits/families/written "
            "artifacts, no leakage across the three split views, balanced family frequencies "
            "within kernel tolerance 0.35, kernel rev- unit-id prefix and uniqueness, "
            "revocation payload present/deterministic/family-shaped with cache modes and "
            "history lengths sweeping their declared spaces, bundled validate_dataset "
            "accepts healthy output) and adversarial (same unit_id in two splits detected "
            "SPLIT_LEAKAGE by the kernel; zero-record and dominant families refused "
            "INVALID_FAMILY_FREQUENCY; unknown split 'holdout' refused UNKNOWN_SPLIT; "
            "unknown family refused UNKNOWN_POPETS_FAMILY; n<=0 refused INVALID_N; no "
            "PHI-named field in any payload or written artifact plus structural placeholder "
            "value checks). baseline_parity=NOT_APPLICABLE: dataset builder, no baseline "
            "arms involved. Regression: full evaluation/venue2027/ = 803 passed. uvx "
            "ruff@0.7.1 clean on evaluation/venue2027/popets/. source_sha_after = base SHA "
            "e5f7ee3b per sibling dataset-task convention: the single task commit is created "
            "immediately after this report and recorded in the commit body."
        ),
    )

    # Proof file lives at research/venue2027/proof/POPETS-dataset.json.
    out_path = REPO / "research/venue2027/proof/POPETS-dataset.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="POPETS-dataset",
        completed_tasks=["POPETS-schema", "SH-schedule_engine"],
        task_dependencies=["POPETS-schema", "SH-schedule_engine"],
    )
    log_path = REPO / "research/venue2027/proof/logs/POPETS-dataset.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
