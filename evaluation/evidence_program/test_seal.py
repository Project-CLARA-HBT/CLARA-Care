from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError, sha256
from evaluation.evidence_program.seal import FROZEN_BINDINGS, HEADLINE_REQUIRED, seal


def _freeze() -> dict[str, object]:
    return {
        "status": "frozen",
        "independent_curator_attestation": True,
        "protocol_version": "v1",
        "freeze_id": "independent-freeze",
        "frozen_at": "2026-08-09T00:00:00Z",
        "code_revision": "clean-sha",
        "cohort_manifest_sha256": "x",
        "annotation_guide_sha256": "x",
        "domain_policy_manifest_sha256": "x",
        "comparator_version": "x",
        "task_manifest_sha256": "x",
        "model_manifest_sha256": "x",
        "statistics_plan_sha256": "x",
    }


def test_seal_rejects_incomplete_headline_artifact(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps(_freeze()), encoding="utf-8")
    with pytest.raises(FreezeError, match="headline_artifacts_missing"):
        seal(tmp_path, freeze)


def test_seal_hashes_every_required_headline_file(tmp_path: Path) -> None:
    freeze = tmp_path / "freeze.json"
    for name in HEADLINE_REQUIRED:
        (tmp_path / name).write_text(name, encoding="utf-8")
    metadata = _freeze()
    metadata["artifact_bindings"] = {name: sha256(tmp_path / name) for name in FROZEN_BINDINGS}
    freeze.write_text(json.dumps(metadata), encoding="utf-8")
    seal_path = seal(tmp_path, freeze)
    payload = json.loads(seal_path.read_text(encoding="utf-8"))
    assert payload["status"] == "sealed_headline_artifact"
    assert set(payload["files"]) == set(HEADLINE_REQUIRED)
