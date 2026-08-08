"""Prepare a privacy-minimised, structural Q3 cohort from lawful local data.

This tool never copies clinical values, medication names, dates, diagnoses or
direct subject identifiers into the evaluation artifact.  It uses source rows
only to establish that a subject has a longitudinal record, then injects a
predeclared *structural* perturbation.  The emitted JSONL is therefore an
oracle-labelled conformance cohort, not a clinical-label dataset.

The source paths are deliberately explicit and must be local.  The tool never
downloads MIMIC, Synthea, or any credentialed dataset.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from collections.abc import Iterable
from pathlib import Path

from evaluation.glhs_q3.run import SCENARIOS

COHORT_SPECS = {
    "mimic_iv_demo": (("hosp/admissions.csv.gz", "hosp/prescriptions.csv.gz"), 100),
    "mimic_iv_ed_demo": (("ed/edstays.csv.gz", "ed/medrecon.csv.gz"), 40),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> Iterable[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as handle:
        yield from csv.DictReader(handle)


def _source_root(path: Path, expected_relatives: tuple[str, ...]) -> Path:
    """Accept either extracted-dataset root or its immediately nested root."""

    if all((path / relative).is_file() for relative in expected_relatives):
        return path
    candidates = [child for child in path.iterdir() if child.is_dir()]
    matching = [
        child
        for child in candidates
        if all((child / relative).is_file() for relative in expected_relatives)
    ]
    if len(matching) == 1:
        return matching[0]
    raise ValueError(f"missing_required_source_tables:{','.join(expected_relatives)}")


def _token(subject_id: str, salt: bytes) -> str:
    return hashlib.sha256(salt + b":" + subject_id.encode("utf-8")).hexdigest()[:32]


def prepare(
    *,
    cohort: str,
    source_root: Path,
    token_salt_file: Path,
    output_dir: Path,
    partition: str,
    lawful_access_attestation: str,
    freeze: dict[str, str] | None,
) -> dict[str, object]:
    if cohort not in COHORT_SPECS:
        raise ValueError("unsupported_cohort")
    if partition not in {"development", "sealed_holdout"}:
        raise ValueError("invalid_partition")
    if not lawful_access_attestation.strip():
        raise ValueError("lawful_access_attestation_required")
    if partition == "sealed_holdout" and freeze is None:
        raise ValueError("sealed_holdout_requires_external_freeze_metadata")

    relatives, minimum_subjects = COHORT_SPECS[cohort]
    root = _source_root(source_root.resolve(), relatives)
    tables = tuple(root / relative for relative in relatives)
    salt = token_salt_file.read_bytes()
    if len(salt) < 16:
        raise ValueError("token_salt_must_be_at_least_16_bytes")

    # We retain only non-reversible tokens and a count of observed source rows.
    source_counts: dict[str, int] = {}
    source_table_rows: dict[str, int] = {}
    source_table_subjects: dict[str, int] = {}
    for table, relative in zip(tables, relatives, strict=True):
        unique_subjects: set[str] = set()
        count = 0
        for row in _rows(table):
            subject_id = row.get("subject_id")
            if subject_id:
                source_counts[subject_id] = source_counts.get(subject_id, 0) + 1
                unique_subjects.add(subject_id)
            count += 1
        source_table_rows[relative] = count
        source_table_subjects[relative] = len(unique_subjects)
    if len(source_counts) < minimum_subjects:
        raise ValueError(f"cohort_has_too_few_distinct_subjects:{len(source_counts)}<{minimum_subjects}")

    output_dir.mkdir(parents=True, exist_ok=True)
    perturbations = output_dir / "perturbations.jsonl"
    rows: list[dict[str, object]] = []
    # The perturbation schedule is fixed before execution.  It depends only on
    # sorted subject IDs and the released source-table checksum—not clinical
    # contents—and remains structurally comparable across cohorts.
    for index, subject_id in enumerate(sorted(source_counts), start=1):
        scenario = SCENARIOS[(index - 1) % len(SCENARIOS)]
        expected_state = "state_current"
        expected_error: str | None = None
        authorized = True
        if scenario in {"conflict", "scribe_ambiguity", "temporal_ambiguity"}:
            expected_state, expected_error = "conflict", "comparable_authority_conflict"
        elif scenario == "insufficient_provenance":
            expected_state, expected_error = "withheld", "insufficient_provenance"
        elif scenario == "family_isolation":
            expected_state, expected_error, authorized = "withheld", "subject_profile_ambiguity", False
        elif scenario == "consent_revocation":
            expected_state, expected_error, authorized = "withheld", "consent_purpose_mismatch", False
        elif scenario == "stale_state_version":
            expected_error = "stale_state_version"
        elif scenario == "direct_write_attack":
            expected_error = "insufficient_corroboration"
        rows.append(
            {
                "case_id": f"{cohort}-{index:03d}",
                "subject_token": _token(subject_id, salt),
                "scenario": scenario,
                "expected_state": expected_state,
                "expected_error": expected_error,
                "critical_fact_count": 3,
                "nonessential_authorized_fact_count": 7,
                "authorized": authorized,
                "episode_count": min(250, max(1, source_counts[subject_id])),
            }
        )
    perturbations.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    manifest: dict[str, object] = {
        "schema_version": "glhs-q3-external-structural-v2",
        "cohort": cohort,
        "partition": partition,
        "lawful_access_attestation": lawful_access_attestation,
        "perturbations_file": perturbations.name,
        "perturbations_sha256": _sha256(perturbations),
        "source_tables_sha256": {
            relative: _sha256(table) for table, relative in zip(tables, relatives, strict=True)
        },
        "source_table_rows": source_table_rows,
        "source_table_subjects": source_table_subjects,
        "source_rows": sum(source_table_rows.values()),
        "source_subjects": len(source_counts),
        "clinical_data_in_output": False,
        "tokenization": "sha256(local_secret_salt:source_subject_id)[:32]",
        "perturbation_policy": "predeclared_structural_cycle_v1",
    }
    if freeze is not None:
        manifest["freeze"] = freeze
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cohort", choices=sorted(COHORT_SPECS), required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--token-salt-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--partition", choices=("development", "sealed_holdout"), default="development")
    parser.add_argument("--lawful-access-attestation", required=True)
    parser.add_argument(
        "--freeze-json",
        type=Path,
        help="Required for sealed holdout; prepared by an independent curator, not generated here.",
    )
    args = parser.parse_args()
    freeze = json.loads(args.freeze_json.read_text(encoding="utf-8")) if args.freeze_json else None
    if freeze is not None and not isinstance(freeze, dict):
        raise TypeError("freeze_json_must_be_object")
    prepare(
        cohort=args.cohort,
        source_root=args.source_root,
        token_salt_file=args.token_salt_file,
        output_dir=args.output,
        partition=args.partition,
        lawful_access_attestation=args.lawful_access_attestation,
        freeze=freeze,
    )


if __name__ == "__main__":
    main()
