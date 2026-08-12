"""Seal v6 cohort and implementation inputs before any development router call."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from evaluation.commitloop.provider import CONFIRMATORY_MODELS, REVIEWER_MODEL
from evaluation.commitloop.run_local import GLHS_BENCH_GLOBAL_CONCURRENCY
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v5_freeze import freeze_inputs
from evaluation.commitloop.v6_cohort import build_cohort, write_cohort


class V6FreezeError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _tracked_worktree_clean(root: Path) -> bool:
    # User-provided datasets and manuscripts may remain untracked; only a
    # tracked implementation change can invalidate this implementation freeze.
    return not _git(root, "status", "--porcelain", "--untracked-files=no")


def create_v6_freeze(*, output_dir: Path, repository_root: Path) -> Path:
    root, output_dir = repository_root.resolve(), output_dir.resolve()
    if output_dir.exists():
        raise V6FreezeError("v6_freeze_output_must_not_exist")
    if not _tracked_worktree_clean(root):
        raise V6FreezeError("v6_freeze_requires_clean_tracked_worktree")
    git_sha = _git(root, "rev-parse", "HEAD")
    output_dir.mkdir(parents=True)
    cohort_path, cohort_manifest_path = write_cohort(output_dir / "cohort")
    rows, generated = build_cohort()
    if len(rows) != 576 or generated["split_counts"] != {
        "development": 96,
        "validation": 96,
        "sealed_test": 384,
    }:
        raise V6FreezeError("v6_cohort_inventory_invalid")
    inputs = freeze_inputs(root)
    payload: dict[str, Any] = {
        "schema_version": "glhs-bench-v6-preprovider-freeze.v1",
        "status": "FROZEN_PRE_PROVIDER",
        "synthetic_software_evaluation_only": True,
        "clinical_adjudication": "NOT_RUN",
        "git_sha": git_sha,
        "provider_calls_before_freeze": 0,
        "cohort_sha256": _sha256(cohort_path),
        "cohort_manifest_sha256": _sha256(cohort_manifest_path),
        "input_sha256": {path: _sha256(root / path) for path in inputs},
        "execution_contract": {
            "models": list(CONFIRMATORY_MODELS),
            "primary_model": REVIEWER_MODEL,
            "conditions": list(CONDITIONS),
            "max_concurrency": GLHS_BENCH_GLOBAL_CONCURRENCY,
            "batch_size": GLHS_BENCH_GLOBAL_CONCURRENCY,
            "max_retries": 2,
            "temperature": 0,
            "response_format": "json_object_with_frozen_local_schema_validation",
            "fallback": False,
            "development_subjects": 96,
            "validation_subjects": 96,
            "sealed_final_subjects": 384,
            "final_holdout_access": "PROHIBITED_UNTIL_FINAL_CANDIDATE_FREEZE",
        },
    }
    freeze_path = output_dir / "freeze.json"
    freeze_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return freeze_path


def verify_v6_freeze(*, freeze_path: Path, repository_root: Path) -> dict[str, Any]:
    payload = json.loads(freeze_path.read_text(encoding="utf-8"))
    root = repository_root.resolve()
    if payload.get("schema_version") != "glhs-bench-v6-preprovider-freeze.v1":
        raise V6FreezeError("v6_freeze_schema_invalid")
    if (
        payload.get("status") != "FROZEN_PRE_PROVIDER"
        or payload.get("provider_calls_before_freeze") != 0
    ):
        raise V6FreezeError("v6_freeze_provider_contract_invalid")
    if not _tracked_worktree_clean(root) or _git(
        root, "rev-parse", "HEAD"
    ) != payload.get("git_sha"):
        raise V6FreezeError("v6_freeze_git_drift")
    inputs = freeze_inputs(root)
    hashes = payload.get("input_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(inputs):
        raise V6FreezeError("v6_freeze_input_inventory_invalid")
    if any(hashes[path] != _sha256(root / path) for path in inputs):
        raise V6FreezeError("v6_freeze_input_drift")
    return payload
