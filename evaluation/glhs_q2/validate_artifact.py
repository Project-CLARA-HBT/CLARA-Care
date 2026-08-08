"""Fail-closed validation for machine-readable GLHS Q2 artifacts.

This validator is deliberately independent of the evaluator's policy logic.
It checks release boundaries and CSV/summary accounting before a result can be
copied into the manuscript.  It accepts the large external-stream artifact in
a streaming pass and never opens raw cohort source data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.glhs_q2.run import SYSTEMS


class ArtifactValidationError(ValueError):
    """Raised when an artifact cannot support a reproducible result claim."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ArtifactValidationError(f"invalid_json:{path.name}") from error
    if not isinstance(value, dict):
        raise ArtifactValidationError(f"json_not_object:{path.name}")
    return value


def _require_metric(metric: object, *, cases: int, label: str) -> None:
    if not isinstance(metric, dict):
        raise ArtifactValidationError(f"metric_not_object:{label}")
    numerator = metric.get("numerator")
    denominator = metric.get("denominator")
    if not isinstance(numerator, int) or not isinstance(denominator, int):
        raise ArtifactValidationError(f"metric_missing_integer_denominator:{label}")
    if denominator != cases or numerator < 0 or numerator > denominator:
        raise ArtifactValidationError(f"metric_out_of_range:{label}")


def _csv_row_count(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def validate(artifact: Path) -> dict[str, object]:
    """Validate a Q2 or external-stream artifact and return an audit object."""

    summary = _read_object(artifact / "summary.json")
    schema = summary.get("schema_version")
    if schema not in {"glhs-q2-structural-v1", "glhs-q2-external-stream-v1"}:
        raise ArtifactValidationError("unsupported_summary_schema")

    if schema == "glhs-q2-external-stream-v1":
        cases = summary.get("cases")
        subjects = summary.get("subjects")
        if not isinstance(cases, int) or cases < 1 or subjects != cases:
            raise ArtifactValidationError("external_case_subject_accounting_invalid")
        if summary.get("partition") != "development":
            raise ArtifactValidationError("external_partition_must_be_development")
        if summary.get("eligible_for_final_score") is not False or summary.get("clinical_validation") is not False:
            raise ArtifactValidationError("external_release_boundary_invalid")
        source_copy = artifact / str(summary.get("source_manifest_copy") or "")
        expected_source_hash = summary.get("source_manifest_sha256")
        if (
            source_copy.name != "source-manifest.json"
            or not source_copy.is_file()
            or not isinstance(expected_source_hash, str)
            or hashlib.sha256(source_copy.read_bytes()).hexdigest() != expected_source_hash
        ):
            raise ArtifactValidationError("external_source_manifest_copy_invalid")
        source_manifest = _read_object(source_copy)
        if source_manifest.get("partition") != "development":
            raise ArtifactValidationError("external_source_manifest_partition_invalid")
        if source_manifest.get("perturbations_sha256") != summary.get("perturbations_sha256"):
            raise ArtifactValidationError("external_source_manifest_checksum_mismatch")
        case_csv = artifact / "external_cases.csv"
        outcome_csv = artifact / "external_outcomes.csv"
        if _csv_row_count(case_csv) != cases:
            raise ArtifactValidationError("external_cases_csv_count_mismatch")
        counts: Counter[str] = Counter()
        with outcome_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                system = row.get("system")
                if system not in SYSTEMS:
                    raise ArtifactValidationError("external_unknown_comparator")
                counts[str(system)] += 1
        expected = {system: cases for system in SYSTEMS}
        if dict(counts) != expected:
            raise ArtifactValidationError("external_outcome_comparator_count_mismatch")
        metrics = summary.get("metrics")
        if not isinstance(metrics, dict) or set(metrics) != set(SYSTEMS):
            raise ArtifactValidationError("external_metrics_comparator_mismatch")
        for system in SYSTEMS:
            system_metrics = metrics[system]
            if not isinstance(system_metrics, dict):
                raise ArtifactValidationError(f"external_metrics_not_object:{system}")
            _require_metric(system_metrics.get("state_correct"), cases=cases, label=f"{system}:state_correct")
        return {
            "valid": True,
            "schema_version": schema,
            "cases": cases,
            "comparators": list(SYSTEMS),
            "final_score_released": False,
        }

    protocol = summary.get("protocol")
    score_release = summary.get("score_release")
    cases = protocol.get("cases") if isinstance(protocol, dict) else None
    if cases != 400:
        raise ArtifactValidationError("q2_case_count_not_exactly_400")
    if not isinstance(score_release, dict) or score_release.get("final_score_released") is not False:
        raise ArtifactValidationError("q2_final_score_release_boundary_invalid")
    evidence = _read_object(artifact / "evidence-manifest.json")
    expected_summary_hash = evidence.get("summary_sha256")
    if not isinstance(expected_summary_hash, str) or len(expected_summary_hash) != 64:
        raise ArtifactValidationError("q2_evidence_manifest_missing_summary_hash")
    actual_summary_hash = hashlib.sha256((artifact / "summary.json").read_bytes()).hexdigest()
    if actual_summary_hash != expected_summary_hash:
        raise ArtifactValidationError("q2_summary_hash_mismatch")
    outcomes = artifact / "outcomes.csv"
    counts: Counter[str] = Counter()
    with outcomes.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            system = row.get("system")
            if system not in SYSTEMS:
                raise ArtifactValidationError("q2_unknown_comparator")
            counts[str(system)] += 1
    if dict(counts) != {system: 400 for system in SYSTEMS}:
        raise ArtifactValidationError("q2_outcome_comparator_count_mismatch")
    return {
        "valid": True,
        "schema_version": schema,
        "cases": 400,
        "comparators": list(SYSTEMS),
        "final_score_released": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(validate(args.artifact), sort_keys=True))


if __name__ == "__main__":
    main()
