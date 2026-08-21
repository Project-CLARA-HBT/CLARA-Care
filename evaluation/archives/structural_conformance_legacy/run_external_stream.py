"""Memory-bounded full external structural-cohort evaluator for Q2.

This runner exists for large lawful synthetic/de-identified manifests such as
the supplied Synthea STU3 archive.  It never opens raw source data: it accepts
only the privacy-minimised perturbation JSONL produced by the preparer, checks
its checksum in a streaming pass, and emits raw CSV plus exact aggregate
structural counts.  It is not a clinical evaluator and cannot release a final
benchmark score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import statistics
from array import array
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evaluation.glhs_q2.run import (
    SCENARIOS,
    SYSTEMS,
    Case,
    Outcome,
    _evaluate,
    _percentile,
    wilson,
)

_ALLOWED_FIELDS = {
    "case_id",
    "subject_token",
    "scenario",
    "expected_state",
    "expected_error",
    "critical_fact_count",
    "nonessential_authorized_fact_count",
    "authorized",
    "episode_count",
}


def _sha256_stream(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _case_from_raw(raw: dict[str, Any], *, partition: str) -> Case:
    if set(raw) != _ALLOWED_FIELDS:
        raise ValueError("external_stream_disallowed_or_missing_field")
    scenario = raw["scenario"]
    if not isinstance(scenario, str) or scenario not in SCENARIOS:
        raise ValueError("external_stream_invalid_scenario")
    if not isinstance(raw["case_id"], str) or not isinstance(raw["subject_token"], str):
        raise TypeError("external_stream_invalid_identifier")
    if not isinstance(raw["expected_state"], str) or (
        raw["expected_error"] is not None and not isinstance(raw["expected_error"], str)
    ):
        raise ValueError("external_stream_invalid_oracle")
    if not isinstance(raw["authorized"], bool) or not all(
        isinstance(raw[field], int) and raw[field] >= 0
        for field in ("episode_count", "critical_fact_count", "nonessential_authorized_fact_count")
    ):
        raise ValueError("external_stream_invalid_structural_field")
    return Case(
        case_id=raw["case_id"],
        subject_id=raw["subject_token"],
        episode_count=raw["episode_count"],
        scenario=scenario,
        expected_state=raw["expected_state"],
        expected_error=raw["expected_error"],
        critical_fact_count=raw["critical_fact_count"],
        nonessential_authorized_fact_count=raw["nonessential_authorized_fact_count"],
        authorized=raw["authorized"],
        experiment="external_structural_full_stream",
        partition=partition,
    )


def _new_counts() -> dict[str, int]:
    return defaultdict(int)


def _record(counts: dict[str, int], outcome: Outcome) -> None:
    counts["cases"] += 1
    for name in (
        "state_correct",
        "late_evidence_error",
        "silent_conflict_collapse",
        "provenance_complete",
        "reconstruction_correct",
        "unauthorized_disclosure",
        "gst_bypass",
        "revocation_honored",
    ):
        counts[name] += int(bool(getattr(outcome, name)))
    counts["critical_fact_numerator"] += round(outcome.critical_fact_recall * 3)
    counts["critical_fact_denominator"] += 3
    counts["nonessential_disclosure"] += outcome.nonessential_disclosure
    if outcome.scenario not in {"family_isolation", "consent_revocation"}:
        counts["nonessential_denominator"] += 7
    counts[f"automation_{outcome.automation}"] += 1


def _ratio(counts: dict[str, int], name: str, *, inverse: bool = False) -> dict[str, object]:
    total = counts["cases"]
    numerator = counts[name]
    if inverse:
        numerator = total - numerator
    lower, upper = wilson(numerator, total)
    return {
        "numerator": numerator,
        "denominator": total,
        "rate": numerator / total,
        "wilson95": [lower, upper],
    }


def _metrics(counts: dict[str, int], latencies: array[float]) -> dict[str, object]:
    return {
        "state_correct": _ratio(counts, "state_correct"),
        "late_evidence_error": _ratio(counts, "late_evidence_error"),
        "silent_conflict_collapse": _ratio(counts, "silent_conflict_collapse"),
        "provenance_complete": _ratio(counts, "provenance_complete"),
        "historical_reconstruction_correct": _ratio(counts, "reconstruction_correct"),
        "unauthorized_disclosure": _ratio(counts, "unauthorized_disclosure"),
        "gst_bypass": _ratio(counts, "gst_bypass"),
        "revocation_honored": _ratio(counts, "revocation_honored"),
        "critical_fact_recall": {
            "numerator": counts["critical_fact_numerator"],
            "denominator": counts["critical_fact_denominator"],
            "rate": counts["critical_fact_numerator"] / counts["critical_fact_denominator"],
        },
        "nonessential_authorized_disclosure": {
            "numerator": counts["nonessential_disclosure"],
            "denominator": counts["nonessential_denominator"],
        },
        "automation": {
            "correct_state": counts["automation_correct_state"],
            "safe_escalation": counts["automation_safe_escalation"],
            "incorrect_automation": counts["automation_incorrect_automation"],
            "denominator": counts["cases"],
        },
        "latency_us_state_layer_simulation": {
            "count": len(latencies),
            "median": statistics.median(latencies),
            "p95": _percentile(list(latencies), 0.95),
            "not_end_to_end_or_llm_latency": True,
        },
    }


def run_stream(*, manifest_path: Path, output: Path) -> dict[str, object]:
    """Evaluate a large perturbation manifest without retaining case rows in RAM."""

    if output.exists():
        raise FileExistsError(f"output_already_exists:{output}")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if not isinstance(manifest, dict) or manifest.get("schema_version") not in {
        "glhs-q2-external-structural-v2",
        "glhs-q3-external-structural-v2",
    }:
        raise ValueError("external_stream_manifest_schema_invalid")
    if manifest.get("partition") != "development":
        raise ValueError("external_stream_requires_development_partition")
    relative = manifest.get("perturbations_file")
    expected_hash = manifest.get("perturbations_sha256")
    if (
        not isinstance(relative, str)
        or Path(relative).is_absolute()
        or not isinstance(expected_hash, str)
    ):
        raise ValueError("external_stream_manifest_perturbation_invalid")
    perturbations = (manifest_path.parent / relative).resolve()
    if manifest_path.parent.resolve() not in perturbations.parents:
        raise ValueError("external_stream_path_escapes_manifest")
    if _sha256_stream(perturbations) != expected_hash:
        raise ValueError("external_stream_checksum_mismatch")

    output.mkdir(parents=True)
    # Copy the already-minimised manifest into the result directory so the
    # CSV/summary artifact remains reviewable after its preparation workspace
    # moves.  It carries checksums/counts only, never raw FHIR resources.
    (output / "source-manifest.json").write_bytes(manifest_bytes)
    case_fields = list(asdict(Case("", "", 0, "", "", None, 0, 0, False, "", "")).keys())
    outcome_fields = list(
        asdict(
            Outcome(
                "",
                "",
                "",
                "",
                False,
                False,
                False,
                False,
                False,
                False,
                0.0,
                0,
                False,
                False,
                "",
                None,
                0.0,
                "",
                "",
            )
        ).keys()
    )
    counts = {system: _new_counts() for system in SYSTEMS}
    latencies = {system: array("d") for system in SYSTEMS}
    # A full Synthea run can contain more than one million rows.  Keep the
    # uniqueness invariant on disk instead of holding every pseudonymous
    # identifier in two Python sets.  The index is ephemeral and contains only
    # identifiers already permitted in the minimised perturbation manifest.
    uniqueness_db = output / ".external-stream-unique.sqlite3"
    uniqueness = sqlite3.connect(uniqueness_db)
    uniqueness.execute("PRAGMA journal_mode=WAL")
    uniqueness.execute(
        "CREATE TABLE identifiers (case_id TEXT PRIMARY KEY NOT NULL, subject_id TEXT UNIQUE NOT NULL)"
    )
    case_count = 0
    with (
        (output / "external_cases.csv").open("w", encoding="utf-8", newline="") as cases_handle,
        (output / "external_outcomes.csv").open(
            "w", encoding="utf-8", newline=""
        ) as outcomes_handle,
        perturbations.open(encoding="utf-8") as source,
    ):
        case_writer = csv.DictWriter(cases_handle, fieldnames=case_fields)
        outcome_writer = csv.DictWriter(outcomes_handle, fieldnames=outcome_fields)
        case_writer.writeheader()
        outcome_writer.writeheader()
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"external_stream_json_invalid:{line_number}") from error
            if not isinstance(raw, dict):
                raise TypeError(f"external_stream_row_invalid:{line_number}")
            case = _case_from_raw(raw, partition="development")
            try:
                uniqueness.execute(
                    "INSERT INTO identifiers (case_id, subject_id) VALUES (?, ?)",
                    (case.case_id, case.subject_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    f"external_stream_duplicate_case_or_subject:{case.case_id}"
                ) from error
            case_count += 1
            case_writer.writerow(asdict(case))
            for system in SYSTEMS:
                outcome = _evaluate(case, system)
                outcome_writer.writerow(asdict(outcome))
                _record(counts[system], outcome)
                latencies[system].append(outcome.latency_us)
            if line_number % 10_000 == 0:
                uniqueness.commit()
                print(f"external_stream cases={line_number}", flush=True)

    uniqueness.commit()
    subjects = int(uniqueness.execute("SELECT COUNT(*) FROM identifiers").fetchone()[0])
    uniqueness.close()
    if not case_count or case_count != subjects:
        raise ValueError("external_stream_requires_one_case_per_unique_subject")
    result = {
        "schema_version": "glhs-q2-external-stream-v1",
        "cohort": manifest.get("cohort"),
        "partition": "development",
        "eligible_for_final_score": False,
        "clinical_validation": False,
        "clinical_data_loaded": False,
        "source_manifest": str(manifest_path.resolve()),
        "source_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "source_manifest_copy": "source-manifest.json",
        "perturbations_sha256": expected_hash,
        "cases": case_count,
        "subjects": subjects,
        "metrics": {system: _metrics(counts[system], latencies[system]) for system in SYSTEMS},
        "limitations": [
            "Pre-derived structural perturbations only; no raw clinical resources were loaded.",
            "Structural oracle conformance only; not clinical validation.",
            "Development partition is ineligible for final benchmark score release.",
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    uniqueness_db.unlink(missing_ok=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run_stream(manifest_path=args.manifest, output=args.output)


if __name__ == "__main__":
    main()
