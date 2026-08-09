"""Prepare a frozen derived EHR cohort from curator-supplied deidentified records.

This utility never downloads EHR data, creates labels, or accepts the synthetic
oracle. It is intended to run by an authorized data steward outside git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from evaluation.evidence_program.freeze import FreezeError

FORBIDDEN_KEYS = frozenset({
    "expected_state", "expected_error", "oracle", "oracle_label", "synthetic",
    "developer_authored", "governance_perturbation",
})
REQUIRED_RECORD_KEYS = frozenset({"subject_token", "task_id", "domain", "index_time"})


def _hash_tokens(tokens: set[str]) -> str:
    return hashlib.sha256("\n".join(sorted(tokens)).encode()).hexdigest()


def prepare(
    input_jsonl: Path,
    output_dir: Path,
    *,
    dataset: str,
    dataset_version: str,
    lawful_attestation: str,
    curator_attestation: str,
    freeze_id: str,
    development_subjects: Path,
) -> Path:
    if not lawful_attestation.strip() or not curator_attestation.strip() or not freeze_id.strip():
        raise FreezeError("lawful_curator_and_freeze_attestations_required")
    development_tokens = {
        line.strip()
        for line in development_subjects.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    rows: list[dict[str, object]] = []
    subjects: set[str] = set()
    domains: Counter[str] = Counter()
    missingness: Counter[str] = Counter()
    with input_jsonl.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FreezeError(f"invalid_jsonl:{line_number}") from exc
            if not isinstance(record, dict) or REQUIRED_RECORD_KEYS - record.keys():
                raise FreezeError(f"record_schema_invalid:{line_number}")
            if FORBIDDEN_KEYS.intersection(record):
                raise FreezeError(f"synthetic_oracle_field_forbidden:{line_number}")
            token = str(record["subject_token"]).strip()
            task_id = str(record["task_id"]).strip()
            domain = str(record["domain"]).strip()
            if not token or not task_id or not domain:
                raise FreezeError(f"record_identity_invalid:{line_number}")
            subjects.add(token)
            domains[domain] += 1
            for key, value in record.items():
                if value is None or value == "":
                    missingness[key] += 1
            rows.append({
                "subject_token": token,
                "task_id": task_id,
                "domain": domain,
                "index_time": record["index_time"],
                "structured_events": record.get("structured_events", []),
            })
    if not rows:
        raise FreezeError("cohort_empty")
    if development_tokens.intersection(subjects):
        raise FreezeError("subject_sets_not_disjoint")
    output_dir.mkdir(parents=True, exist_ok=True)
    derived = output_dir / "records.jsonl"
    with derived.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest = {
        "status": "frozen",
        "partition": "sealed_holdout",
        "freeze_id": freeze_id,
        "dataset": dataset,
        "dataset_version": dataset_version,
        "lawful_access_attestation": lawful_attestation,
        "curator_attestation": curator_attestation,
        "independent_curator": True,
        "subject_count": len(subjects),
        "event_count": sum(domains.values()),
        "domain_coverage": dict(sorted(domains.items())),
        "missingness": dict(sorted(missingness.items())),
        "test_subject_tokens_sha256": _hash_tokens(subjects),
        "development_subject_tokens_sha256": _hash_tokens(development_tokens),
        "inclusion_exclusion": "curator-supplied pre-frozen selection",
        "selection_frozen_at": freeze_id,
        "source_checksum": hashlib.sha256(input_jsonl.read_bytes()).hexdigest(),
        "synthetic_governance_separate": True,
        "derived_records_sha256": hashlib.sha256(derived.read_bytes()).hexdigest(),
    }
    manifest_path = output_dir / "cohort_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--lawful-attestation", required=True)
    parser.add_argument("--curator-attestation", required=True)
    parser.add_argument("--freeze-id", required=True)
    parser.add_argument("--development-subjects", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(prepare(
            args.input_jsonl,
            args.output_dir,
            dataset=args.dataset,
            dataset_version=args.dataset_version,
            lawful_attestation=args.lawful_attestation,
            curator_attestation=args.curator_attestation,
            freeze_id=args.freeze_id,
            development_subjects=args.development_subjects,
        ))
    except FreezeError as exc:
        parser.error(str(exc))
