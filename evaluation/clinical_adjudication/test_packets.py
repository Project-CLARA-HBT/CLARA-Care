from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from evaluation.clinical_adjudication.packets import (
    disagreement_packets,
    export_packets,
    import_adjudications,
    import_labels,
)
from evaluation.evidence_program.freeze import FreezeError


def _input(path: Path) -> None:
    path.write_text(json.dumps({"case_id": "secure-case-1", "review_payload": {"timeline": ["deidentified event"]}, "fields": ["current_state"]}) + "\n", encoding="utf-8")


def test_blinded_export_import_and_disagreement_packets(tmp_path: Path) -> None:
    source, guide, packets = tmp_path / "input.jsonl", tmp_path / "guide.md", tmp_path / "packets"
    _input(source)
    guide.write_text("rubric", encoding="utf-8")
    manifest = export_packets(input_path=source, output_dir=packets, annotation_guide=guide, reviewer_ids=("reviewer-a", "reviewer-b"), blinding_salt="a-long-controlled-test-salt")
    assert manifest["status"] == "READY_FOR_EXTERNAL_ADJUDICATION"
    packet = json.loads((packets / "blinded_packets.jsonl").read_text(encoding="utf-8"))
    assert "secure-case-1" not in (packets / "blinded_packets.jsonl").read_text(encoding="utf-8")
    labels = tmp_path / "labels.csv"
    with labels.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["packet_id", "annotator_id", "field", "label"])
        writer.writeheader()
        writer.writerows([
            {"packet_id": packet["packet_id"], "annotator_id": "reviewer-a", "field": "current_state", "label": "active"},
            {"packet_id": packet["packet_id"], "annotator_id": "reviewer-b", "field": "current_state", "label": "resolved"},
        ])
    imported = tmp_path / "labels.normalized.csv"
    result = import_labels(labels_path=labels, packet_dir=packets, output_path=imported)
    assert result["row_count"] == 2
    assert "secure-case-1" in imported.read_text(encoding="utf-8")
    adjudication = tmp_path / "disagreements.json"
    report = disagreement_packets(labels_path=labels, packet_dir=packets, output_path=adjudication)
    assert report["disagreement_count"] == 1
    packet_row = json.loads(adjudication.read_text(encoding="utf-8"))["disagreements"][0]
    assert packet_row["field"] == "current_state"
    assert "secure-case-1" not in adjudication.read_text(encoding="utf-8")
    annotation_manifest = tmp_path / "annotation.json"
    annotation_manifest.write_text(json.dumps({
        "status": "frozen", "annotation_guide_sha256": "guide-sha", "annotator_ids": ["reviewer-a", "reviewer-b"],
        "adjudicator_id": "adjudicator-c", "oracle_sha256": "oracle-sha", "blinding": "system-blinded",
    }), encoding="utf-8")
    decisions = tmp_path / "decisions.csv"
    with decisions.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["packet_id", "adjudicator_id", "field", "final_label", "rationale"])
        writer.writeheader()
        writer.writerow({"packet_id": packet_row["packet_id"], "adjudicator_id": "adjudicator-c", "field": "current_state", "final_label": "active", "rationale": "documented human rationale"})
    final = tmp_path / "final.csv"
    adjudicated = import_adjudications(adjudications_path=decisions, disagreement_path=adjudication, packet_dir=packets, annotation_manifest_path=annotation_manifest, output_path=final)
    assert adjudicated["decision_count"] == 1
    assert "secure-case-1" in final.read_text(encoding="utf-8")


def test_export_rejects_system_identity_in_reviewer_payload(tmp_path: Path) -> None:
    source, guide = tmp_path / "input.jsonl", tmp_path / "guide.md"
    source.write_text(json.dumps({"case_id": "case", "review_payload": {"model": "forbidden"}, "fields": ["x"]}) + "\n", encoding="utf-8")
    guide.write_text("rubric", encoding="utf-8")
    with pytest.raises(FreezeError, match="system_identity_or_outcome"):
        export_packets(input_path=source, output_dir=tmp_path / "packets", annotation_guide=guide, reviewer_ids=("a", "b"), blinding_salt="a-long-controlled-test-salt")
