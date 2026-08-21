"""Validate frozen common-offset tasks without upgrading them to clinical truth."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

TASK_FIELDS = frozenset(
    {
        "task_id",
        "subject_token",
        "encounter_token",
        "domain",
        "slot_fingerprint",
        "structured_events",
        "source_target_event_id",
        "ground_truth_kind",
        "knowledge_time_status",
    }
)
EVENT_FIELDS = frozenset(
    {
        "event_id",
        "source_index",
        "valid_offset_minutes",
        "value_fingerprint",
        "source_pointer_sha256",
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
        raise TypeError("offset_task_json_invalid")
    return payload


def validate(
    tasks_path: Path,
    manifest_path: Path,
    normalization_freeze_path: Path,
    source_manifest_path: Path,
) -> dict[str, object]:
    manifest = _json(manifest_path)
    if (
        manifest.get("schema_version") != "clara-common-offset-source-tasks.v1"
        or manifest.get("status") != "FROZEN_DEVELOPER_PREPARED_SOURCE_DERIVED"
        or manifest.get("clinical_oracle") is not False
        or manifest.get("headline_eligible") is not False
        or manifest.get("knowledge_time_status") != "UNAVAILABLE_NOT_ESTIMATED"
    ):
        raise ValueError("offset_task_manifest_contract_invalid")
    stored_payload_hash = manifest.get("manifest_payload_sha256")
    unsigned = dict(manifest)
    unsigned.pop("manifest_payload_sha256", None)
    observed_payload_hash = hashlib.sha256(_canonical(unsigned).encode()).hexdigest()
    if stored_payload_hash != observed_payload_hash:
        raise ValueError("offset_task_manifest_hash_mismatch")
    if manifest.get("tasks_sha256") != _sha_file(tasks_path):
        raise ValueError("offset_task_file_hash_mismatch")
    code_revision = manifest.get("code_revision")
    if not isinstance(code_revision, str) or not re.fullmatch(r"[0-9a-f]{40}", code_revision):
        raise ValueError("offset_task_code_revision_invalid")
    root = Path(__file__).resolve().parents[2]
    commit = subprocess.run(
        ["git", "cat-file", "-e", f"{code_revision}^{{commit}}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if commit.returncode:
        raise ValueError("offset_task_code_revision_missing")
    source_manifest = _json(source_manifest_path)
    normalization_freeze = _json(normalization_freeze_path)
    normalization_evidence = normalization_freeze.get("evidence")
    if not isinstance(normalization_evidence, dict):
        raise TypeError("offset_task_normalization_freeze_invalid")
    normalization = normalization_evidence.get("normalization")
    if not isinstance(normalization, dict):
        raise TypeError("offset_task_normalization_freeze_invalid")
    if (
        manifest.get("source_manifest_payload_sha256")
        != source_manifest.get("manifest_payload_sha256")
        or manifest.get("normalized_records_sha256") != normalization.get("records_sha256")
        or manifest.get("normalization_manifest_sha256")
        != normalization_evidence.get("normalization_manifest_sha256")
    ):
        raise ValueError("offset_task_upstream_binding_mismatch")
    task_ids: set[str] = set()
    subjects: set[str] = set()
    counts: Counter[str] = Counter()
    with tasks_path.open(encoding="utf-8") as stream:
        for line in stream:
            task = json.loads(line)
            if not isinstance(task, dict) or set(task) != TASK_FIELDS:
                raise ValueError("offset_task_fields_invalid")
            task_id = str(task["task_id"])
            subject_token = str(task["subject_token"])
            encounter_token = str(task["encounter_token"])
            if (
                not re.fullmatch(r"[0-9a-f]{24}", task_id)
                or not re.fullmatch(r"[0-9a-f]{32}", subject_token)
                or not re.fullmatch(r"[0-9a-f]{32}", encounter_token)
                or task_id in task_ids
            ):
                raise ValueError("offset_task_identity_invalid")
            if (
                task["ground_truth_kind"] != "source_offset_derived_not_clinician_adjudicated"
                or task["knowledge_time_status"] != "UNAVAILABLE_NOT_ESTIMATED"
            ):
                raise ValueError("offset_task_claim_boundary_invalid")
            events = task.get("structured_events")
            if not isinstance(events, list) or len(events) < 2:
                raise ValueError("offset_task_events_invalid")
            event_ids: set[str] = set()
            offsets = []
            for event in events:
                if not isinstance(event, dict) or set(event) != EVENT_FIELDS:
                    raise ValueError("offset_task_event_fields_invalid")
                if not isinstance(event.get("valid_offset_minutes"), int):
                    raise TypeError("offset_task_event_offset_invalid")
                event_id = str(event["event_id"])
                if not re.fullmatch(r"[0-9a-f]{24}", event_id) or event_id in event_ids:
                    raise ValueError("offset_task_event_identity_invalid")
                for field in ("value_fingerprint", "source_pointer_sha256"):
                    if not re.fullmatch(r"[0-9a-f]{64}", str(event[field])):
                        raise ValueError("offset_task_event_hash_invalid")
                event_ids.add(event_id)
                offsets.append(int(event["valid_offset_minutes"]))
            latest = max(offsets)
            if offsets.count(latest) != 1:
                raise ValueError("offset_task_latest_tie_not_excluded")
            selected = events[offsets.index(latest)]["event_id"]
            if task["source_target_event_id"] != selected:
                raise ValueError("offset_task_source_target_invalid")
            task_ids.add(task_id)
            subjects.add(subject_token)
            counts["tasks"] += 1
            counts["events"] += len(events)
            counts[f"domain:{task['domain']}"] += 1
    domain_counts = {
        key.removeprefix("domain:"): value
        for key, value in sorted(counts.items())
        if key.startswith("domain:")
    }
    if (
        counts["tasks"] != manifest.get("task_count")
        or counts["events"] != manifest.get("event_count")
        or len(subjects) != manifest.get("represented_evaluation_subject_count")
        or domain_counts != manifest.get("domain_task_counts")
    ):
        raise ValueError("offset_task_aggregate_mismatch")
    return {
        "schema_version": "clara-common-offset-source-tasks-validation.v1",
        "status": "VALID_FROZEN_SOURCE_OFFSET_TASKS",
        "task_count": counts["tasks"],
        "event_count": counts["events"],
        "subject_count": len(subjects),
        "domain_task_counts": domain_counts,
        "manifest_payload_sha256": stored_payload_hash,
        "tasks_sha256": manifest["tasks_sha256"],
        "claim_limit": manifest["claim_limit"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--normalization-freeze", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(
            args.tasks,
            args.manifest,
            args.normalization_freeze,
            args.source_manifest,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
