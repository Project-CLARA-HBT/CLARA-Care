from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.external_validation.prepare_cohort import prepare


def _write(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def test_preparer_freezes_deidentified_subject_disjoint_cohort(tmp_path: Path) -> None:
    source = _write(tmp_path / "source.jsonl", json.dumps({
        "subject_token": "sealed-subject-1",
        "task_id": "task-1",
        "domain": "medication",
        "index_time": "2026-01-01T00:00:00Z",
        "structured_events": [],
    }) + "\n")
    development = _write(tmp_path / "development.txt", "development-subject-1\n")
    manifest_path = prepare(
        source,
        tmp_path / "derived",
        dataset="mimic_iv",
        dataset_version="curator-version",
        lawful_attestation="lawful access",
        curator_attestation="independent curator",
        freeze_id="freeze-1",
        development_subjects=development,
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["partition"] == "sealed_holdout"
    assert manifest["subject_count"] == 1
    assert manifest["synthetic_governance_separate"] is True


def test_preparer_rejects_synthetic_oracle_and_overlap(tmp_path: Path) -> None:
    source = _write(tmp_path / "source.jsonl", json.dumps({
        "subject_token": "shared",
        "task_id": "task-1",
        "domain": "medication",
        "index_time": "2026-01-01T00:00:00Z",
        "expected_state": "oracle",
    }) + "\n")
    development = _write(tmp_path / "development.txt", "shared\n")
    with pytest.raises(FreezeError, match="synthetic_oracle_field_forbidden"):
        prepare(
            source,
            tmp_path / "derived",
            dataset="mimic_iv",
            dataset_version="curator-version",
            lawful_attestation="lawful access",
            curator_attestation="independent curator",
            freeze_id="freeze-1",
            development_subjects=development,
        )
