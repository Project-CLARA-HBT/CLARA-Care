"""Validate a frozen non-clinical eICU source-offset GLHS execution."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from evaluation.external_validation.run_common_offset_glhs import (
    PROTOCOL_SCHEMA_VERSION,
    PROTOCOL_STATUS,
    SCHEMA_VERSION,
    SYSTEMS,
)

REQUIRED_FILES = frozenset(
    {
        "checksums.sha256",
        "domain_results.csv",
        "report.md",
        "run_manifest.json",
        "subject_results.csv",
        "system_outputs.jsonl.gz",
    }
)


def _canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("common_offset_result_json_invalid")
    return payload


def _payload_hash(payload: dict[str, Any], field: str) -> str:
    stored = payload.get(field)
    unsigned = dict(payload)
    unsigned.pop(field, None)
    if stored != hashlib.sha256(_canonical(unsigned).encode()).hexdigest():
        raise ValueError(f"common_offset_result_hash_mismatch:{field}")
    return str(stored)


def _verify_checksums(output_dir: Path) -> None:
    observed_files = {path.name for path in output_dir.iterdir() if path.is_file()}
    if observed_files != REQUIRED_FILES:
        raise ValueError("common_offset_result_file_set_invalid")
    declared: dict[str, str] = {}
    for line in (output_dir / "checksums.sha256").read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 2 or parts[1] in declared:
            raise ValueError("common_offset_result_checksum_inventory_invalid")
        declared[parts[1]] = parts[0]
    expected = REQUIRED_FILES - {"checksums.sha256"}
    if set(declared) != expected:
        raise ValueError("common_offset_result_checksum_file_set_invalid")
    for name in expected:
        if declared[name] != _sha_file(output_dir / name):
            raise ValueError(f"common_offset_result_checksum_mismatch:{name}")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _count_row(row: dict[str, str], *, key_field: str) -> tuple[tuple[str, str], tuple[int, int]]:
    system = row.get("system", "")
    key = row.get(key_field, "")
    if system not in SYSTEMS or not key:
        raise ValueError("common_offset_result_aggregate_identity_invalid")
    try:
        correct = int(row["correct"])
        total = int(row["total"])
        rate = float(row["rate"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("common_offset_result_aggregate_numeric_invalid") from exc
    if total <= 0 or not 0 <= correct <= total or not math.isfinite(rate):
        raise ValueError("common_offset_result_aggregate_range_invalid")
    if not math.isclose(rate, correct / total, rel_tol=0, abs_tol=1e-12):
        raise ValueError("common_offset_result_aggregate_rate_invalid")
    return (key, system), (correct, total)


def validate(
    output_dir: Path,
    tasks_path: Path,
    cohort_manifest_path: Path,
    protocol_path: Path,
) -> dict[str, object]:
    if not output_dir.is_dir():
        raise ValueError("common_offset_result_directory_missing")
    _verify_checksums(output_dir)
    protocol = _json(protocol_path)
    cohort = _json(cohort_manifest_path)
    manifest = _json(output_dir / "run_manifest.json")
    _payload_hash(protocol, "protocol_payload_sha256")
    _payload_hash(cohort, "manifest_payload_sha256")
    _payload_hash(manifest, "manifest_payload_sha256")
    if (
        protocol.get("schema_version") != PROTOCOL_SCHEMA_VERSION
        or protocol.get("status") != PROTOCOL_STATUS
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("status") != "PASS"
        or manifest.get("systems") != list(SYSTEMS)
        or manifest.get("clinical_oracle") is not False
        or manifest.get("headline_eligible") is not False
        or manifest.get("provider_calls") != 0
        or manifest.get("execution_boundary") != "in_process_api_owned_service_layer_sqlite"
        or manifest.get("postgresql_or_http_measured") is not False
    ):
        raise ValueError("common_offset_result_contract_invalid")
    if (
        manifest.get("tasks_sha256") != _sha_file(tasks_path)
        or manifest.get("cohort_manifest_sha256") != _sha_file(cohort_manifest_path)
        or manifest.get("protocol_file_sha256") != _sha_file(protocol_path)
        or manifest.get("protocol_payload_sha256") != protocol.get("protocol_payload_sha256")
        or protocol.get("tasks_sha256") != manifest.get("tasks_sha256")
        or protocol.get("cohort_manifest_sha256") != manifest.get("cohort_manifest_sha256")
    ):
        raise ValueError("common_offset_result_input_binding_mismatch")
    task_count = 0
    event_count = 0
    subjects: set[str] = set()
    domain_counts: Counter[tuple[str, str]] = Counter()
    subject_counts: Counter[tuple[str, str]] = Counter()
    subject_totals: Counter[tuple[str, str]] = Counter()
    system_counts: Counter[str] = Counter()
    system_missing: Counter[str] = Counter()
    with gzip.open(output_dir / "system_outputs.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if not isinstance(row, dict) or set(row) != {
                "task_id",
                "subject_token",
                "domain",
                "source_target_event_id",
                "systems",
                "error_code",
            }:
                raise ValueError("common_offset_result_row_fields_invalid")
            if row["error_code"]:
                raise ValueError("common_offset_result_contains_error")
            subject = str(row["subject_token"])
            target = str(row["source_target_event_id"])
            domain = str(row["domain"])
            if (
                not re.fullmatch(r"[0-9a-f]{32}", subject)
                or not re.fullmatch(r"[0-9a-f]{24}", str(row["task_id"]))
                or not re.fullmatch(r"[0-9a-f]{24}", target)
                or not isinstance(row["systems"], dict)
                or set(row["systems"]) != set(SYSTEMS)
            ):
                raise ValueError("common_offset_result_row_identity_invalid")
            subjects.add(subject)
            task_count += 1
            for system in SYSTEMS:
                result = row["systems"][system]
                if not isinstance(result, dict) or set(result) != {
                    "selected_event_id",
                    "correct",
                    "status",
                }:
                    raise ValueError("common_offset_result_system_fields_invalid")
                selected = result["selected_event_id"]
                if selected is not None and not re.fullmatch(r"[0-9a-f]{24}", str(selected)):
                    raise ValueError("common_offset_result_selection_invalid")
                correct = selected == target and selected is not None
                if result["correct"] is not correct or result["status"] != (
                    "PASS" if correct else "FAIL"
                ):
                    raise ValueError("common_offset_result_score_invalid")
                system_counts[system] += int(correct)
                system_missing[system] += int(selected is None)
                domain_counts[(domain, system)] += int(correct)
                subject_counts[(subject, system)] += int(correct)
                subject_totals[(subject, system)] += 1
    with tasks_path.open(encoding="utf-8") as stream:
        for line in stream:
            task = json.loads(line)
            events = task.get("structured_events") if isinstance(task, dict) else None
            if not isinstance(events, list):
                raise TypeError("common_offset_result_task_input_invalid")
            event_count += len(events)
    if task_count != manifest.get("task_count") or event_count != manifest.get("event_count"):
        raise ValueError("common_offset_result_task_event_count_mismatch")
    if len(subjects) != manifest.get("subject_count"):
        raise ValueError("common_offset_result_subject_count_mismatch")
    subject_declared = dict(
        _count_row(row, key_field="subject_token")
        for row in _read_csv(output_dir / "subject_results.csv")
    )
    expected_subjects = {key: (subject_counts[key], total) for key, total in subject_totals.items()}
    if subject_declared != expected_subjects:
        raise ValueError("common_offset_result_subject_aggregate_mismatch")
    domain_totals: Counter[tuple[str, str]] = Counter()
    with gzip.open(output_dir / "system_outputs.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            for system in SYSTEMS:
                domain_totals[(str(row["domain"]), system)] += 1
    domain_declared = dict(
        _count_row(row, key_field="domain") for row in _read_csv(output_dir / "domain_results.csv")
    )
    expected_domains = {key: (domain_counts[key], total) for key, total in domain_totals.items()}
    if domain_declared != expected_domains:
        raise ValueError("common_offset_result_domain_aggregate_mismatch")
    declared_systems = manifest.get("system_results")
    if not isinstance(declared_systems, dict):
        raise TypeError("common_offset_result_system_aggregate_invalid")
    for system in SYSTEMS:
        if declared_systems.get(system) != {
            "correct": system_counts[system],
            "total": task_count,
            "missing": system_missing[system],
        }:
            raise ValueError("common_offset_result_system_aggregate_mismatch")
    primary = manifest.get("primary_result")
    if primary != {
        "correct": task_count,
        "total": task_count,
        "missing": 0,
        "pass": True,
    }:
        raise ValueError("common_offset_result_primary_invariant_failed")
    if system_counts[SYSTEMS[0]] != task_count or system_missing[SYSTEMS[0]]:
        raise ValueError("common_offset_result_reference_invariant_failed")
    row_counts = manifest.get("row_counts")
    if not isinstance(row_counts, dict) or any(
        row_counts.get(name) != event_count
        for name in ("evidence", "assertions", "transitions", "state_versions")
    ):
        raise ValueError("common_offset_result_production_row_count_invalid")
    return {
        "schema_version": "clara-common-offset-glhs-validation.v1",
        "status": "VALID",
        "subjects": len(subjects),
        "tasks": task_count,
        "events": event_count,
        "production_glhs_correct": system_counts[SYSTEMS[2]],
        "strong_reference_correct": system_counts[SYSTEMS[0]],
        "input_order_correct": system_counts[SYSTEMS[1]],
        "claim_limit": manifest["claim_limit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.output, args.tasks, args.cohort_manifest, args.protocol)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "INVALID", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
