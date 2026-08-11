"""Freeze source-derived within-encounter tasks from common offset records.

Targets come only from observable source offsets. They are not clinical labels,
and this preparer never compares offsets across encounters or invents knowledge
time.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, TextIO

DOMAINS = frozenset(
    {"allergies_adverse_reactions", "diagnoses_problems", "medications", "observations"}
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _file_sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _git_sha(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _stream(path: Path) -> Iterable[str]:
    if path.suffix == ".gz":
        stream: TextIO
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            yield from stream
        return
    with path.open(encoding="utf-8") as stream:
        yield from stream


def _offset(record: Mapping[str, Any]) -> int | None:
    value = record.get("valid_time")
    if not isinstance(value, dict) or value.get("anchor") != "icu_unit_admission":
        return None
    for field in ("start_offset_minutes", "offset_minutes", "end_offset_minutes"):
        candidate = value.get(field)
        if isinstance(candidate, int):
            return candidate
    return None


def _slot(record: Mapping[str, Any]) -> str | None:
    domain = record.get("domain")
    value = record.get("original_value")
    if not isinstance(value, dict):
        return None
    candidates = {
        "allergies_adverse_reactions": ("drugname", "allergyname"),
        "diagnoses_problems": ("icd9code", "diagnosisstring"),
        "medications": ("drugname",),
        "observations": ("labname",),
    }.get(str(domain), ())
    parts = [str(value.get(field, "")).strip() for field in candidates]
    selected = [part for part in parts if part]
    return "|".join(selected) if selected else None


def _partition(subject: str) -> str:
    return (
        "development"
        if int(_sha({"subject": subject, "split": "v1"}), 16) % 5 == 0
        else "evaluation"
    )


def prepare(
    records_path: Path,
    normalization_manifest_path: Path,
    source_manifest_path: Path,
    output_dir: Path,
    *,
    freeze_id: str,
    dataset_id: str,
    dataset_version: str,
) -> dict[str, object]:
    if output_dir.exists():
        raise ValueError("offset_task_output_exists")
    if not freeze_id.strip():
        raise ValueError("offset_task_freeze_id_required")
    normalization = json.loads(normalization_manifest_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
    if (
        normalization.get("dataset_id") != dataset_id
        or normalization.get("status") != "COMPLETE"
        or normalization.get("records_sha256") != _file_sha(records_path)
    ):
        raise ValueError("offset_task_normalization_binding_invalid")
    if source_manifest.get("dataset_id") != dataset_id:
        raise ValueError("offset_task_source_binding_invalid")
    groups: dict[tuple[str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    subjects: set[str] = set()
    processed = 0
    excluded_missing_offset = 0
    excluded_missing_slot = 0
    for source_index, line in enumerate(_stream(records_path), start=1):
        record = json.loads(line)
        if not isinstance(record, dict) or record.get("domain") not in DOMAINS:
            continue
        processed += 1
        subject = str(record.get("source_subject", ""))
        encounter = str(record.get("encounter_id", ""))
        if not subject or not encounter:
            raise ValueError("offset_task_identity_missing")
        subjects.add(subject)
        valid_offset = _offset(record)
        if valid_offset is None:
            excluded_missing_offset += 1
            continue
        raw_slot = _slot(record)
        if raw_slot is None:
            excluded_missing_slot += 1
            continue
        domain = str(record["domain"])
        slot_fingerprint = _sha({"domain": domain, "slot": raw_slot})[:24]
        event_id = _sha(
            {
                "source_record_id": record.get("source_record_id"),
                "payload": record.get("original_payload_sha256"),
            }
        )[:24]
        groups[(subject, encounter, domain, slot_fingerprint)].append(
            {
                "event_id": event_id,
                "source_index": source_index,
                "valid_offset_minutes": valid_offset,
                "value_fingerprint": _sha(record.get("original_value")),
                "source_pointer_sha256": _sha(record.get("original_payload_pointer")),
            }
        )
    development_subjects = {subject for subject in subjects if _partition(subject) == "development"}
    evaluation_subjects = subjects - development_subjects
    if development_subjects & evaluation_subjects:
        raise AssertionError("offset_task_split_not_disjoint")
    tasks: list[dict[str, object]] = []
    excluded_short_groups = 0
    excluded_latest_ties = 0
    domain_counts: dict[str, int] = defaultdict(int)
    represented_subjects: set[str] = set()
    task_event_count = 0
    for (subject, encounter, domain, slot), events in sorted(groups.items()):
        if subject not in evaluation_subjects:
            continue
        if len(events) < 2:
            excluded_short_groups += 1
            continue
        event_offsets = [event["valid_offset_minutes"] for event in events]
        if not all(isinstance(value, int) for value in event_offsets):
            raise ValueError("offset_task_event_offset_invalid")
        latest = max(value for value in event_offsets if isinstance(value, int))
        targets = [event for event in events if event["valid_offset_minutes"] == latest]
        if len(targets) != 1:
            excluded_latest_ties += 1
            continue
        subject_token = _sha({"dataset": dataset_id, "subject": subject})[:32]
        encounter_token = _sha({"dataset": dataset_id, "encounter": encounter})[:32]
        represented_subjects.add(subject_token)
        domain_counts[domain] += 1
        task_event_count += len(events)
        tasks.append(
            {
                "task_id": _sha(
                    {
                        "subject_token": subject_token,
                        "encounter_token": encounter_token,
                        "domain": domain,
                        "slot": slot,
                    }
                )[:24],
                "subject_token": subject_token,
                "encounter_token": encounter_token,
                "domain": domain,
                "slot_fingerprint": slot,
                "structured_events": events,
                "source_target_event_id": targets[0]["event_id"],
                "ground_truth_kind": "source_offset_derived_not_clinician_adjudicated",
                "knowledge_time_status": "UNAVAILABLE_NOT_ESTIMATED",
            }
        )
    if not tasks:
        raise ValueError("offset_tasks_empty")
    output_dir.mkdir(parents=True)
    tasks_path = output_dir / "tasks.jsonl"
    tasks_path.write_text(
        "".join(json.dumps(task, sort_keys=True) + "\n" for task in tasks),
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    manifest = {
        "schema_version": "clara-common-offset-source-tasks.v1",
        "status": "FROZEN_DEVELOPER_PREPARED_SOURCE_DERIVED",
        "freeze_id": freeze_id,
        "code_revision": _git_sha(root),
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "partition": "subject_disjoint_evaluation_from_deterministic_development_split",
        "selection_method": "sha256(dataset-local source subject) deterministic 20/80 split before task selection",
        "comparison_scope": "within one ICU unit stay and one source-derived slot only",
        "development_subject_count": len(development_subjects),
        "evaluation_source_subject_count": len(evaluation_subjects),
        "represented_evaluation_subject_count": len(represented_subjects),
        "development_evaluation_disjoint": True,
        "processed_domain_record_count": processed,
        "task_count": len(tasks),
        "event_count": task_event_count,
        "domain_task_counts": dict(sorted(domain_counts.items())),
        "exclusions": {
            "missing_valid_offset": excluded_missing_offset,
            "missing_slot": excluded_missing_slot,
            "fewer_than_two_events": excluded_short_groups,
            "latest_offset_tie": excluded_latest_ties,
        },
        "tasks_sha256": _file_sha(tasks_path),
        "normalization_manifest_sha256": _file_sha(normalization_manifest_path),
        "normalized_records_sha256": normalization["records_sha256"],
        "source_manifest_payload_sha256": source_manifest["manifest_payload_sha256"],
        "knowledge_time_status": "UNAVAILABLE_NOT_ESTIMATED",
        "independent_curator": False,
        "clinical_oracle": False,
        "headline_eligible": False,
        "planned_systems": [
            "valid_offset_resolver_strong_parity_reference",
            "input_order_baseline",
            "production_glhs_projection_pending_adapter",
        ],
        "claim_limit": "source_derived_within_encounter_temporal_structure_not_clinical_correctness",
    }
    manifest["manifest_payload_sha256"] = _sha(manifest)
    (output_dir / "cohort_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--normalization-manifest", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--freeze-id", required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    args = parser.parse_args()
    prepare(
        args.records,
        args.normalization_manifest,
        args.source_manifest,
        args.output,
        freeze_id=args.freeze_id,
        dataset_id=args.dataset_id,
        dataset_version=args.dataset_version,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
