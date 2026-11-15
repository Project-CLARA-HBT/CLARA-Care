"""Emit research/venue2027/proof/PST-dataset.json via agent_protocol.build_report.

Builds the task report for the PST-dataset deliverable with real log paths
captured during verification, then validates it with
``agent_protocol.validate_report`` and records the validator result in
``research/venue2027/proof/logs/PST-dataset.validator.log``.
"""

from __future__ import annotations

import json
import pathlib
import sys

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "_shared" / "tools"
sys.path.insert(0, str(TOOLS))

import agent_protocol as ap  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[3]
BASE = "604642528f95e9f10052bd4bc0334bdb1c84358a"

CHANGED = [
    "evaluation/venue2027/pst/__init__.py",
    "evaluation/venue2027/pst/generate_dataset.py",
    "evaluation/venue2027/pst/test_generate_dataset.py",
    "research/venue2027/proof/artifacts/pst_dataset/manifest.json",
    "research/venue2027/proof/artifacts/pst_dataset/inventory.json",
    "research/venue2027/proof/artifacts/pst_dataset/records.jsonl",
    "research/venue2027/proof/logs/PST-dataset.pytest.log",
    "research/venue2027/proof/logs/PST-dataset.ruff.log",
    "research/venue2027/proof/logs/PST-dataset.suite.log",
    "research/venue2027/proof/logs/PST-dataset.artifact.log",
    "research/venue2027/proof/logs/PST-dataset.validator.log",
    "research/venue2027/proof/PST-dataset.json",
]


def main() -> int:
    report = ap.build_report(
        task_id="PST-dataset",
        status="PASS",
        source_sha_before=BASE,
        source_sha_after=BASE,
        changed_paths=CHANGED,
        commands=[
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/pst/test_generate_dataset.py",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-dataset.pytest.log",
            },
            {
                "argv": "uvx ruff@0.7.1 check evaluation/venue2027/pst/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-dataset.ruff.log",
            },
            {
                "argv": (
                    "python3 -m evaluation.venue2027.pst.generate_dataset "
                    "--outdir research/venue2027/proof/artifacts/pst_dataset "
                    "--seed 2027 --n 120"
                ),
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-dataset.artifact.log",
            },
            {
                "argv": "python3 -m pytest -q evaluation/venue2027/",
                "exit_code": 0,
                "log_path": "research/venue2027/proof/logs/PST-dataset.suite.log",
            },
        ],
        artifact_paths=[
            "evaluation/venue2027/pst/generate_dataset.py",
            "evaluation/venue2027/pst/test_generate_dataset.py",
            "research/venue2027/proof/artifacts/pst_dataset/manifest.json",
            "research/venue2027/proof/artifacts/pst_dataset/inventory.json",
            "research/venue2027/proof/artifacts/pst_dataset/records.jsonl",
            "research/venue2027/proof/logs/PST-dataset.pytest.log",
            "research/venue2027/proof/logs/PST-dataset.ruff.log",
            "research/venue2027/proof/logs/PST-dataset.suite.log",
            "research/venue2027/proof/logs/PST-dataset.artifact.log",
        ],
        repo=REPO,
        oracle_disagreement_count=0,
        baseline_parity="NOT_APPLICABLE",
        unresolved=[],
        notes=(
            "P02 deterministic dataset and split builder for ReceiptMin (PST 2027): "
            "generate(seed, split, n) -> Dataset delegates all record construction to the "
            "audited shared kernel dataset_kernel.generate('pst', ...) (kernel v1.0.0 pinned; "
            "venue families full_evidence / minimized_omission / receipt_anchored / "
            "linkability_leak; unit prefix aud) and layers the PST-specific payload "
            "deterministically from the kernel determinant via pure integer modular "
            "arithmetic (no random module, no clock, no environment): audit_retention_mode in "
            "{full, selective, hash_only} with retention_epoch (RQ3 retention epochs), "
            "omitted_field_count + omitted_fields over the six structural receipt fields "
            "(ground-truth minimization signal: full_evidence omits nothing, "
            "minimized_omission drops the retention-mode tail, receipt_anchored drops "
            "witness_id + retention_mode - the PST-CASE-05 overredaction shape; "
            "linkability_leak omits nothing because its leak is the purpose_tag disclosure "
            "surface, PST-CASE-06), receipt_present (true for all four families - the "
            "PST-CASE-09 no-log comparator is a baseline arm, not a record family), and "
            "query_set_id over the ex-ante frozen forensic query set {QS-forensic-bounded, "
            "QS-retention-decay, QS-linkage-bound} (RQ1 method architecture). Content hash is "
            "split-independent and byte-identical for repeated (seed, n): dataset "
            "content_sha256 2e1fd1a6843be8a9bb7f025156d2c5c626c6cd2f59c67f080f6431f02292512d, "
            "records_sha256 e3e620678faa87df9e4549efc7ecfa76be7fe8425a6271d95dd78ac244997b71 "
            "(seed 2027, n=120; train 72 / dev 24 / test 24; 30 records per family; "
            "synthetic_only=true, phi_fields=[]). write_dataset(outdir, seed, n) runs the "
            "fail-closed validators (assert_valid_frequencies + assert_no_leakage via "
            "per-split regeneration) BEFORE any file is written, then persists records.jsonl / "
            "inventory.json / manifest.json; a validation failure leaves the output directory "
            "absent (crash-clean). Real dataset artifact committed at "
            "research/venue2027/proof/artifacts/pst_dataset/. 25 tests (14 positive incl. "
            "kernel delegation identity, determinism, split-independence, family ground-truth "
            "omission encoding, retention-mode/query-set distribution, write determinism and "
            "idempotency; 11 adversarial incl. UNKNOWN_SPLIT, INVALID_N, UNKNOWN_PST_FAMILY, "
            "PHI_FIELD_PRESENT, SPLIT_LEAKAGE, INVALID_FAMILY_FREQUENCY with no directory "
            "created, kernel registry drift guard, cross-venue unit-id collision guard) pass; "
            "uvx ruff@0.7.1 clean; full evaluation/venue2027/ regression 510 passed. "
            "source_sha_after = base commit 60464252 per sibling dataset-task convention "
            "(IFIP_SEC-dataset, DIMVA-dataset): the single task commit is created immediately "
            "after this report and recorded in the commit body."
        ),
    )

    # Proof file lives at research/venue2027/proof/PST-dataset.json.
    out_path = REPO / "research/venue2027/proof/PST-dataset.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = ap.validate_report(
        json.loads(out_path.read_text(encoding="utf-8")),
        repo=REPO,
        expected_task_id="PST-dataset",
        completed_tasks=["PST-schema", "SH-schedule_engine"],
        task_dependencies=["PST-schema", "SH-schedule_engine"],
    )
    log_path = REPO / "research/venue2027/proof/logs/PST-dataset.validator.log"
    log_path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
