from __future__ import annotations

import json
from pathlib import Path

from evaluation.domain_portability.run_source_derived import run


def test_source_derived_runner_reports_each_domain_without_clinical_claim(tmp_path: Path) -> None:
    records = tmp_path / "records.jsonl"
    tasks = []
    for index, domain in enumerate(("medication", "diagnosis_problem", "lab_state"), 1):
        tasks.append(
            {
                "task_id": f"task-{index}",
                "subject_token": "subject-token",
                "domain": domain,
                "index_time": "2026-01-02T00:00:00+00:00",
                "ground_truth_kind": "source_timestamp_derived_not_clinician_adjudicated",
                "structured_events": [
                    {
                        "event_id": f"old-{index}",
                        "valid_time": "2026-01-01T00:00:00+00:00",
                        "knowledge_time": "2026-01-03T00:00:00+00:00",
                        "value_fingerprint": "old",
                    },
                    {
                        "event_id": f"new-{index}",
                        "valid_time": "2026-01-02T00:00:00+00:00",
                        "knowledge_time": "2026-01-02T00:00:00+00:00",
                        "value_fingerprint": "new",
                    },
                ],
            }
        )
    records.write_text("".join(json.dumps(task) + "\n" for task in tasks), encoding="utf-8")
    summary = run(records, tmp_path / "out")
    assert summary["status"] == "completed_not_clinician_adjudicated"
    assert summary["domains"] == ["diagnosis_problem", "lab_state", "medication"]
    assert summary["eligible_tasks"] == 3
