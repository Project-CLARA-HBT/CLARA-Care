"""Validate the immutable contract required before a headline GovMut run.

The development matrix deliberately cannot become a final benchmark by changing
one status field.  This validator binds every reviewed input to its local bytes
and refuses a denominator that is not backed by dual-model non-equivalence
results. It does not execute mutants or validate clinical claims.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from evaluation.evidence_program.freeze import FreezeError, sha256
from evaluation.property_assurance.suite_matrix import METHOD_IDS

_SCHEMA_VERSION = "govmut-final-freeze.v1"
_REVIEW_SCHEMA_VERSION = "govmut-dual-model-review.v1"
_GIT_REVISION = re.compile(r"^[0-9a-f]{40}$")
_REVIEW_DISPOSITIONS = frozenset({"included", "excluded_equivalent", "excluded_unexecutable", "unresolved"})
_REVIEW_MODEL_IDS = ("gemini-3.6-flash-high", "claude-sonnet-4-6")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError("govmut_final_freeze_invalid_json") from exc
    if not isinstance(value, dict):
        raise FreezeError("govmut_final_freeze_not_object")
    return value


def _require_sha256(value: object, error: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise FreezeError(error)
    return value


def _catalog_ids(catalog_path: Path) -> set[str]:
    catalog = _load_json(catalog_path)
    candidates = catalog.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise FreezeError("govmut_final_freeze_catalog_invalid")
    ids = [item.get("id") for item in candidates if isinstance(item, dict)]
    if len(ids) != len(candidates) or not all(isinstance(item, str) and item for item in ids):
        raise FreezeError("govmut_final_freeze_catalog_invalid")
    if len(set(ids)) != len(ids):
        raise FreezeError("govmut_final_freeze_catalog_duplicate_ids")
    return set(ids)


def _current_revision(repository_root: Path) -> str:
    """Resolve the exact reviewed source revision rather than trusting metadata."""

    try:
        return subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise FreezeError("govmut_final_freeze_repository_revision_unavailable") from exc


def _validate_target_hashes(*, repository_root: Path, methods: object) -> None:
    if not isinstance(methods, dict) or set(methods) != set(METHOD_IDS):
        raise FreezeError("govmut_final_freeze_methods_invalid")
    for method in METHOD_IDS:
        definition = methods[method]
        if not isinstance(definition, dict):
            raise FreezeError("govmut_final_freeze_method_invalid")
        targets = definition.get("targets")
        hashes = definition.get("target_sha256")
        if not isinstance(targets, list) or not targets or not all(isinstance(item, str) for item in targets):
            raise FreezeError("govmut_final_freeze_targets_invalid")
        if len(set(targets)) != len(targets) or not isinstance(hashes, dict) or set(hashes) != set(targets):
            raise FreezeError("govmut_final_freeze_target_hashes_invalid")
        for target in targets:
            relative, _, _selector = target.partition("::")
            path = (repository_root / relative).resolve()
            try:
                path.relative_to(repository_root.resolve())
            except ValueError as exc:
                raise FreezeError("govmut_final_freeze_target_outside_repository") from exc
            if not path.is_file() or _require_sha256(hashes[target], "govmut_final_freeze_target_hash_invalid") != sha256(path):
                raise FreezeError("govmut_final_freeze_target_hash_mismatch")


def _validate_review_artifact(*, manifest_path: Path, review: object, expected_ids: set[str]) -> None:
    if (
        not isinstance(review, dict)
        or review.get("status") != "dual_model_reviewed"
        or review.get("model_ids") != list(_REVIEW_MODEL_IDS)
        or not isinstance(review.get("artifact"), str)
        or not review["artifact"].strip()
    ):
        raise FreezeError("govmut_final_freeze_non_equivalence_review_invalid")
    artifact = (manifest_path.parent / review["artifact"]).resolve()
    try:
        artifact.relative_to(manifest_path.parent.resolve())
    except ValueError as exc:
        raise FreezeError("govmut_final_freeze_review_artifact_outside_manifest") from exc
    if not artifact.is_file():
        raise FreezeError("govmut_final_freeze_review_artifact_missing")
    if _require_sha256(review.get("results_sha256"), "govmut_final_freeze_review_artifact_hash_invalid") != sha256(artifact):
        raise FreezeError("govmut_final_freeze_review_artifact_hash_mismatch")

    artifact_review = _load_json(artifact)
    dispositions = artifact_review.get("dispositions")
    if (
        artifact_review.get("schema_version") != _REVIEW_SCHEMA_VERSION
        or artifact_review.get("model_ids") != list(_REVIEW_MODEL_IDS)
        or not isinstance(dispositions, list)
    ):
        raise FreezeError("govmut_final_freeze_review_artifact_invalid")
    reviewed_ids: list[str] = []
    final_dispositions: list[str] = []
    for disposition in dispositions:
        if (
            not isinstance(disposition, dict)
            or not isinstance(disposition.get("mutant_id"), str)
            or disposition["mutant_id"] not in expected_ids
            or disposition.get("disposition") not in _REVIEW_DISPOSITIONS
            or not isinstance(disposition.get("model_dispositions"), dict)
            or set(disposition["model_dispositions"]) != set(_REVIEW_MODEL_IDS)
            or not all(value in _REVIEW_DISPOSITIONS for value in disposition["model_dispositions"].values())
        ):
            raise FreezeError("govmut_final_freeze_review_disposition_invalid")
        reviewed_ids.append(disposition["mutant_id"])
        final_dispositions.append(disposition["disposition"])
    if (
        len(reviewed_ids) != len(set(reviewed_ids))
        or set(reviewed_ids) != expected_ids
        or "included" not in final_dispositions
    ):
        raise FreezeError("govmut_final_freeze_review_disposition_coverage_invalid")


def validate_final_freeze(
    *, manifest_path: Path, repository_root: Path, catalog_path: Path, statistics_plan_path: Path
) -> dict[str, Any]:
    """Validate a reviewed locked-run manifest against the current local bytes."""

    manifest = _load_json(manifest_path)
    required = {
        "schema_version", "status", "study_id", "freeze_id", "code_revision",
        "catalog_sha256", "statistics_plan_sha256", "methods", "hypothesis",
        "limits", "non_equivalence_review",
    }
    if required - set(manifest):
        raise FreezeError("govmut_final_freeze_fields_missing")
    if (
        manifest["schema_version"] != _SCHEMA_VERSION
        or manifest["status"] != "frozen"
        or manifest["study_id"] != "assurance-soict-2026"
        or not isinstance(manifest["freeze_id"], str)
        or not manifest["freeze_id"].strip()
        or not isinstance(manifest["code_revision"], str)
        or not _GIT_REVISION.fullmatch(manifest["code_revision"])
    ):
        raise FreezeError("govmut_final_freeze_identity_invalid")
    if manifest["code_revision"] != _current_revision(repository_root):
        raise FreezeError("govmut_final_freeze_code_revision_mismatch")
    if _require_sha256(manifest["catalog_sha256"], "govmut_final_freeze_catalog_hash_invalid") != sha256(catalog_path):
        raise FreezeError("govmut_final_freeze_catalog_hash_mismatch")
    if _require_sha256(manifest["statistics_plan_sha256"], "govmut_final_freeze_statistics_hash_invalid") != sha256(statistics_plan_path):
        raise FreezeError("govmut_final_freeze_statistics_hash_mismatch")
    _validate_target_hashes(repository_root=repository_root, methods=manifest["methods"])

    hypothesis = manifest["hypothesis"]
    if not isinstance(hypothesis, dict) or not isinstance(hypothesis.get("version"), str) or not hypothesis["version"].strip():
        raise FreezeError("govmut_final_freeze_hypothesis_invalid")
    seeds = hypothesis.get("ordered_seeds")
    if not isinstance(seeds, list) or not seeds or not all(isinstance(seed, int) and seed > 0 for seed in seeds) or len(set(seeds)) != len(seeds):
        raise FreezeError("govmut_final_freeze_seeds_invalid")

    limits = manifest["limits"]
    required_limits = {"pytest_timeout_seconds", "hypothesis_max_examples", "hypothesis_stateful_step_count"}
    if not isinstance(limits, dict) or required_limits - set(limits) or not all(isinstance(limits[key], int) and limits[key] > 0 for key in required_limits):
        raise FreezeError("govmut_final_freeze_limits_invalid")

    _validate_review_artifact(
        manifest_path=manifest_path,
        review=manifest["non_equivalence_review"],
        expected_ids=_catalog_ids(catalog_path),
    )
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--statistics-plan", type=Path, required=True)
    args = parser.parse_args()
    try:
        validate_final_freeze(
            manifest_path=args.manifest,
            repository_root=args.repository_root,
            catalog_path=args.catalog,
            statistics_plan_path=args.statistics_plan,
        )
    except FreezeError as exc:
        parser.error(str(exc))
