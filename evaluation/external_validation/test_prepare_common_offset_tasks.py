from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.external_validation.prepare_common_offset_tasks import (
    _partition,
    prepare,
)
from evaluation.external_validation.validate_common_offset_tasks import validate


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preparer_keeps_offsets_within_encounter_and_marks_nonclinical(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    subject = next(
        f"evaluation-subject-{index}"
        for index in range(100)
        if _partition(f"evaluation-subject-{index}") == "evaluation"
    )
    rows = []
    for index, offset in enumerate((5, 10), start=1):
        rows.append(
            {
                "source_subject": subject,
                "encounter_id": "stay-1",
                "domain": "observations",
                "source_record_id": f"lab-{index}",
                "original_payload_sha256": f"{index}" * 64,
                "original_payload_pointer": f"source#L{index}",
                "original_value": {"labname": "Hct", "labresult": str(index)},
                "valid_time": {
                    "anchor": "icu_unit_admission",
                    "offset_minutes": offset,
                },
            }
        )
    records.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    normalization = {
        "dataset_id": "fixture",
        "status": "COMPLETE",
        "records_sha256": _sha(records),
    }
    normalization_path = tmp_path / "normalization_manifest.json"
    normalization_path.write_text(json.dumps(normalization), encoding="utf-8")
    source_path = tmp_path / "source_manifest.json"
    source_path.write_text(
        json.dumps(
            {
                "dataset_id": "fixture",
                "manifest_payload_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )

    manifest = prepare(
        records,
        normalization_path,
        source_path,
        tmp_path / "out",
        freeze_id="fixture-freeze",
        dataset_id="fixture",
        dataset_version="1",
    )

    assert manifest["clinical_oracle"] is False
    assert manifest["headline_eligible"] is False
    assert manifest["knowledge_time_status"] == "UNAVAILABLE_NOT_ESTIMATED"
    assert manifest["task_count"] == 1
    task = json.loads((tmp_path / "out" / "tasks.jsonl").read_text(encoding="utf-8"))
    assert task["source_target_event_id"] == task["structured_events"][1]["event_id"]
    assert all("source_subject" not in event for event in task["structured_events"])
    normalization_freeze_path = tmp_path / "normalization_freeze.json"
    normalization_freeze_path.write_text(
        json.dumps(
            {
                "evidence": {
                    "normalization": normalization,
                    "normalization_manifest_sha256": _sha(normalization_path),
                }
            }
        ),
        encoding="utf-8",
    )
    validation = validate(
        tmp_path / "out" / "tasks.jsonl",
        tmp_path / "out" / "cohort_manifest.json",
        normalization_freeze_path,
        source_path,
    )
    assert validation["status"] == "VALID_FROZEN_SOURCE_OFFSET_TASKS"

    task["source_target_event_id"] = task["structured_events"][0]["event_id"]
    tasks_path = tmp_path / "out" / "tasks.jsonl"
    tasks_path.write_text(json.dumps(task, sort_keys=True) + "\n", encoding="utf-8")
    manifest["tasks_sha256"] = _sha(tasks_path)
    manifest.pop("manifest_payload_sha256")
    manifest["manifest_payload_sha256"] = hashlib.sha256(
        json.dumps(
            manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()
    (tmp_path / "out" / "cohort_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="offset_task_source_target_invalid"):
        validate(
            tasks_path,
            tmp_path / "out" / "cohort_manifest.json",
            normalization_freeze_path,
            source_path,
        )
