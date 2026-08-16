from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.clinical_adjudication.analyze import analyze
from evaluation.clinical_adjudication.validate_manifest import validate
from evaluation.evidence_program.freeze import FreezeError


def test_agreement_report_preserves_field_level_disagreement(tmp_path: Path) -> None:
    manifest = {
        "status": "frozen",
        "annotation_guide_sha256": "guide-sha",
        "annotator_ids": ["qualified-a", "qualified-b"],
        "adjudicator_id": "qualified-c",
        "oracle_sha256": "oracle-sha",
        "blinding": "system-blinded",
        "reviewer_qualifications": {
            "qualified-a": {"role_code": "licensed_clinician", "eligibility_attested": True, "independence_attested": True},
            "qualified-b": {"role_code": "licensed_clinician", "eligibility_attested": True, "independence_attested": True},
            "qualified-c": {"role_code": "licensed_clinician", "eligibility_attested": True, "independence_attested": True},
        },
    }
    manifest_path = tmp_path / "annotation.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    labels_path = tmp_path / "labels.csv"
    with labels_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["case_id", "annotator_id", "field", "label"])
        writer.writeheader()
        writer.writerows([
            {"case_id": "c1", "annotator_id": "qualified-a", "field": "current_state", "label": "active"},
            {"case_id": "c1", "annotator_id": "qualified-b", "field": "current_state", "label": "active"},
            {"case_id": "c2", "annotator_id": "qualified-a", "field": "current_state", "label": "resolved"},
            {"case_id": "c2", "annotator_id": "qualified-b", "field": "current_state", "label": "active"},
        ])
    report = analyze(labels_path, manifest_path)
    field = report["fields"]["current_state"]
    assert field["paired_cases"] == 2
    assert field["agreements"] == 1
    assert field["disagreements"] == 1
    assert field["disagreement_rate"] == 0.5


def test_annotation_manifest_requires_exactly_two_pseudonymous_reviewers(tmp_path: Path) -> None:
    manifest = {
        "status": "frozen",
        "annotation_guide_sha256": "guide-sha",
        "annotator_ids": ["reviewer-a", "reviewer-b", "reviewer-c"],
        "adjudicator_id": "adjudicator-d",
        "oracle_sha256": "oracle-sha",
        "blinding": "system-blinded",
        "reviewer_qualifications": {
            reviewer: {"role_code": "licensed_clinician", "eligibility_attested": True, "independence_attested": True}
            for reviewer in ("reviewer-a", "reviewer-b", "reviewer-c", "adjudicator-d")
        },
    }
    path = tmp_path / "annotation.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(FreezeError, match="independent_annotation_not_ready"):
        validate(path)
