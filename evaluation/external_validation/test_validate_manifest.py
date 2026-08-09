from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.evidence_program.freeze import FreezeError
from evaluation.external_validation.validate_manifest import validate


def _token_hash(tokens: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(tokens)).encode()).hexdigest()


def _manifest(development: list[str], test: list[str]) -> dict[str, object]:
    return {
        "status": "frozen",
        "dataset": "mimic_iv",
        "dataset_version": "required-curator-value",
        "lawful_access_attestation": "curator-provided",
        "partition": "sealed_holdout",
        "subject_count": len(test),
        "test_subject_tokens_sha256": _token_hash(test),
        "development_subject_tokens_sha256": _token_hash(development),
        "inclusion_exclusion": "curator-provided",
        "event_count": 1,
        "domain_coverage": {"medication": 1},
        "missingness": {},
        "curator_attestation": "curator-provided",
        "independent_curator": True,
        "selection_frozen_at": "2026-08-09T00:00:00Z",
        "source_checksum": "curator-permitted",
        "synthetic_governance_separate": True,
    }


def _write(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_external_manifest_requires_subject_disjointness(tmp_path: Path) -> None:
    development, test = ["salted-dev-a"], ["salted-test-a", "salted-test-b"]
    manifest = tmp_path / "manifest.json"
    dev_path, test_path = tmp_path / "dev.txt", tmp_path / "test.txt"
    manifest.write_text(json.dumps(_manifest(development, test)), encoding="utf-8")
    _write(dev_path, development)
    _write(test_path, test)
    validate(manifest, dev_path, test_path)


def test_external_manifest_rejects_subject_overlap(tmp_path: Path) -> None:
    development, test = ["salted-shared"], ["salted-shared"]
    manifest = tmp_path / "manifest.json"
    dev_path, test_path = tmp_path / "dev.txt", tmp_path / "test.txt"
    manifest.write_text(json.dumps(_manifest(development, test)), encoding="utf-8")
    _write(dev_path, development)
    _write(test_path, test)
    with pytest.raises(FreezeError, match="subject_sets_not_disjoint"):
        validate(manifest, dev_path, test_path)
