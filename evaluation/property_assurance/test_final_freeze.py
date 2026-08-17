from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.property_assurance import final_freeze
from evaluation.property_assurance.final_freeze import validate_final_freeze


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _manifest(root: Path, catalog: Path, statistics: Path) -> dict[str, object]:
    target = root / "tests/test_contract.py"
    targets = ["tests/test_contract.py"]
    return {
        "schema_version": "govmut-final-freeze.v1",
        "status": "frozen",
        "study_id": "assurance-soict-2026",
        "freeze_id": "controlled-freeze-001",
        "code_revision": "a" * 40,
        "catalog_sha256": _hash(catalog),
        "statistics_plan_sha256": _hash(statistics),
        "methods": {method: {"targets": targets, "target_sha256": {targets[0]: _hash(target)}} for method in ("M0_regression", "M1_stateless_property", "M2_state_machine", "M3_combined")},
        "hypothesis": {"version": "6.0", "ordered_seeds": [17, 23]},
        "limits": {"pytest_timeout_seconds": 120, "hypothesis_max_examples": 100, "hypothesis_stateful_step_count": 25},
        "non_equivalence_review": {
            "status": "dual_model_reviewed",
            "model_ids": ["gemini-3.6-flash-high", "claude-sonnet-4-6"],
            "artifact": "dual-model-review.json",
            "results_sha256": _hash(catalog.parent / "dual-model-review.json"),
        },
    }


def _files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    root = tmp_path / "repository"
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "tests/test_contract.py").write_text("def test_contract(): pass\n", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"candidates": [{"id": "M01-A"}, {"id": "M02-A"}]}), encoding="utf-8")
    review = tmp_path / "dual-model-review.json"
    review.write_text(json.dumps({
        "schema_version": "govmut-dual-model-review.v1",
        "model_ids": ["gemini-3.6-flash-high", "claude-sonnet-4-6"],
        "dispositions": [
            {"mutant_id": "M01-A", "disposition": "included", "model_dispositions": {"gemini-3.6-flash-high": "included", "claude-sonnet-4-6": "included"}},
            {"mutant_id": "M02-A", "disposition": "excluded_equivalent", "model_dispositions": {"gemini-3.6-flash-high": "excluded_equivalent", "claude-sonnet-4-6": "excluded_equivalent"}},
        ],
    }), encoding="utf-8")
    statistics = tmp_path / "statistics.json"
    statistics.write_text("{}", encoding="utf-8")
    manifest = tmp_path / "freeze.json"
    manifest.write_text(json.dumps(_manifest(root, catalog, statistics)), encoding="utf-8")
    return root, catalog, statistics, manifest


def test_final_freeze_binds_all_reviewed_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, catalog, statistics, manifest = _files(tmp_path)
    monkeypatch.setattr(final_freeze, "_current_revision", lambda _root: "a" * 40)
    assert validate_final_freeze(manifest_path=manifest, repository_root=root, catalog_path=catalog, statistics_plan_path=statistics)["status"] == "frozen"


def test_final_freeze_rejects_changed_review_artifact_or_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, catalog, statistics, manifest = _files(tmp_path)
    monkeypatch.setattr(final_freeze, "_current_revision", lambda _root: "a" * 40)
    (tmp_path / "dual-model-review.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FreezeError, match="govmut_final_freeze_review_artifact_hash_mismatch"):
        validate_final_freeze(manifest_path=manifest, repository_root=root, catalog_path=catalog, statistics_plan_path=statistics)
    root, catalog, statistics, manifest = _files(tmp_path)
    manifest.write_text(json.dumps(_manifest(root, catalog, statistics)), encoding="utf-8")
    (root / "tests/test_contract.py").write_text("def test_contract(): assert False\n", encoding="utf-8")
    with pytest.raises(FreezeError, match="govmut_final_freeze_target_hash_mismatch"):
        validate_final_freeze(manifest_path=manifest, repository_root=root, catalog_path=catalog, statistics_plan_path=statistics)


def test_final_freeze_requires_one_valid_disposition_per_catalog_mutant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, catalog, statistics, manifest = _files(tmp_path)
    monkeypatch.setattr(final_freeze, "_current_revision", lambda _root: "a" * 40)
    review = tmp_path / "dual-model-review.json"
    value = json.loads(review.read_text(encoding="utf-8"))
    value["dispositions"].pop()
    review.write_text(json.dumps(value), encoding="utf-8")
    manifest_value = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_value["non_equivalence_review"]["results_sha256"] = _hash(review)
    manifest.write_text(json.dumps(manifest_value), encoding="utf-8")

    with pytest.raises(FreezeError, match="govmut_final_freeze_review_disposition_coverage_invalid"):
        validate_final_freeze(manifest_path=manifest, repository_root=root, catalog_path=catalog, statistics_plan_path=statistics)


def test_final_freeze_rejects_manifest_for_a_different_code_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, catalog, statistics, manifest = _files(tmp_path)
    monkeypatch.setattr(final_freeze, "_current_revision", lambda _root: "b" * 40)

    with pytest.raises(FreezeError, match="govmut_final_freeze_code_revision_mismatch"):
        validate_final_freeze(
            manifest_path=manifest,
            repository_root=root,
            catalog_path=catalog,
            statistics_plan_path=statistics,
        )
