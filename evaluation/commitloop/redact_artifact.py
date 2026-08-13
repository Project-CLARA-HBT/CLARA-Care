"""Deterministically repair a sealed run artifact blocked by PHI redaction checks.

This utility is deliberately limited to the non-executable frozen cohort copy.
It never changes model inputs, outputs, scores, or the original provider-time
freeze.  A pre-repair checksum is retained as a documented deviation before a
new seal is written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from evaluation.commitloop.run_local import seal_artifacts
from evaluation.commitloop.v6_runner import sanitize_artifact_cohort


def repair_artifact_cohort_redaction(run_dir: Path) -> dict[str, object]:
    """Redact FHIR subject references in a completed non-final run artifact."""

    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = str(manifest.get("source_cohort", ""))
    if not source.startswith("glhs_bench_") or source.rsplit(":", 1)[-1] not in {
        "development",
        "validation",
    }:
        raise ValueError("artifact_redaction_requires_nonfinal_glhs_bench_run")
    split = source.rsplit(":", 1)[-1]
    inputs = run_dir / "frozen_inputs"
    cohort_path = inputs / f"cohort_{split}.jsonl"
    provenance_path = inputs / "artifact_provenance.json"
    checksum_path = run_dir / "checksums.sha256"
    if not cohort_path.is_file() or not provenance_path.is_file() or not checksum_path.is_file():
        raise ValueError("artifact_redaction_inputs_missing")
    original_cohort_sha256 = hashlib.sha256(cohort_path.read_bytes()).hexdigest()
    prior_checksums_sha256 = hashlib.sha256(checksum_path.read_bytes()).hexdigest()
    rows = [json.loads(line) for line in cohort_path.read_text(encoding="utf-8").splitlines() if line]
    sanitized_rows: list[dict[str, object]] = []
    redactions = 0
    for row in rows:
        sanitized, count = sanitize_artifact_cohort(row)
        if not isinstance(sanitized, dict):  # pragma: no cover - JSONL rows are objects by contract
            raise TypeError("artifact_redaction_row_invalid")
        sanitized_rows.append(sanitized)
        redactions += count
    if redactions < 1:
        raise ValueError("artifact_redaction_no_subject_references_found")
    cohort_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in sanitized_rows),
        encoding="utf-8",
    )
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if not isinstance(provenance, dict):
        raise TypeError("artifact_redaction_provenance_invalid")
    provenance["schema_version"] = "glhs-bench-v6-run-inputs.v2"
    provenance["selected_cohort_sha256"] = hashlib.sha256(cohort_path.read_bytes()).hexdigest()
    provenance["redaction"] = {
        "algorithm": "fhir_subject_reference_v1",
        "subject_reference_redactions": redactions,
    }
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    deviation = {
        "schema_version": "glhs-bench-artifact-redaction-repair.v1",
        "reason": "validator_forbidden_fhir_subject_reference",
        "scope": "frozen_inputs_cohort_copy_only",
        "model_outputs_modified": False,
        "scoring_modified": False,
        "provider_calls_made": False,
        "original_cohort_sha256": original_cohort_sha256,
        "prior_checksums_sha256": prior_checksums_sha256,
        "redaction": provenance["redaction"],
    }
    (run_dir / "artifact_redaction_deviation.json").write_text(
        json.dumps(deviation, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    seal_artifacts(run_dir)
    return deviation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    result = repair_artifact_cohort_redaction(args.run_dir)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
