from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance.w9_human_review import validate_human_review_gate


def _write_review_inputs(tmp_path: Path, *, llm_calls: bool = False) -> Path:
    catalog = tmp_path / "w9_catalog.json"
    catalog.write_text(
        json.dumps({"candidates": [{"id": "W9-C01"}, {"id": "W9-C02"}]}),
        encoding="utf-8",
    )
    review = tmp_path / "w9_human_review.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": "govmut-w9-human-review.v1",
                "status": "completed",
                "review_mode": "human_manual",
                "llm_calls": llm_calls,
                "reviewers": [
                    {
                        "reviewer_id": "R-01",
                        "background": "verification engineer",
                        "independence_declaration": "independent of outcomes",
                        "review_date": "2026-08-19",
                    }
                ],
                "candidates": [
                    {
                        "case_id": case_id,
                        "packet_ref": f"w9_review_manifest.json#{case_id}",
                        "reviewer_dispositions": {
                            "R-01": {
                                "label": "NON_EQUIVALENT",
                                "rationale": "The overlay changes governed behavior.",
                            }
                        },
                        "final_disposition": "included",
                    }
                    for case_id in ("W9-C01", "W9-C02")
                ],
                "completed_at": "2026-08-19T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    digest = hashlib.sha256(review.read_bytes()).hexdigest()
    manifest = tmp_path / "w9_final_freeze.json"
    manifest.write_text(
        json.dumps(
            {
                "human_review": {
                    "status": "completed",
                    "artifact": review.name,
                    "results_sha256": digest,
                }
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_human_review_gate_requires_completed_artifact(tmp_path: Path) -> None:
    manifest = _write_review_inputs(tmp_path)
    review = validate_human_review_gate(
        manifest_path=manifest, catalog_path=tmp_path / "w9_catalog.json"
    )
    assert review["review_mode"] == "human_manual"


def test_human_review_gate_rejects_llm_review(tmp_path: Path) -> None:
    manifest = _write_review_inputs(tmp_path, llm_calls=True)
    with pytest.raises(FreezeError, match="govmut_w9_human_review_artifact_invalid"):
        validate_human_review_gate(
            manifest_path=manifest, catalog_path=tmp_path / "w9_catalog.json"
        )


def test_human_review_gate_rejects_open_gate(tmp_path: Path) -> None:
    catalog = tmp_path / "w9_catalog.json"
    catalog.write_text(json.dumps({"candidates": [{"id": "W9-C01"}]}), encoding="utf-8")
    manifest = tmp_path / "w9_final_freeze.json"
    manifest.write_text(json.dumps({"human_review": {"status": "MANUAL_REQUIRED"}}), encoding="utf-8")
    with pytest.raises(FreezeError, match="govmut_w9_human_review_gate_open"):
        validate_human_review_gate(manifest_path=manifest, catalog_path=catalog)


def test_human_review_gate_rejects_label_disposition_mismatch(tmp_path: Path) -> None:
    manifest = _write_review_inputs(tmp_path)
    review = tmp_path / "w9_human_review.json"
    payload = json.loads(review.read_text(encoding="utf-8"))
    payload["candidates"][0]["final_disposition"] = "excluded_equivalent"
    review.write_text(json.dumps(payload), encoding="utf-8")
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_payload["human_review"]["results_sha256"] = hashlib.sha256(
        review.read_bytes()
    ).hexdigest()
    manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_w9_human_review_final_disposition_invalid"):
        validate_human_review_gate(
            manifest_path=manifest, catalog_path=tmp_path / "w9_catalog.json"
        )
