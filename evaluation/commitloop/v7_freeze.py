"""Seal the v7 confirmatory cohort and implementation inputs before any router call.

The v7 cohort must be source-disjoint from the sealed v5/v6 evidence.  The
freeze therefore requires a prior-cohort exclusion registry (schema
``commitloop-prior-cohort-exclusions.v1``, the registry pattern sealed by
``v5_freeze.py``) and fails closed with ``v7_prior_cohort_registry_required``
when neither an explicit registry file nor at least one sealed prior run
(``--prior-run``) is supplied.  No registry currently exists under
``evaluation/commitloop/`` or ``artifacts/``, so a v7 freeze may only be
created with an explicit registry or sealed prior v5/v6 run directories.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
)
from evaluation.commitloop.run_local import (
    GLHS_BENCH_GLOBAL_CONCURRENCY,
    expected_solver_case_count,
)
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v5_freeze import freeze_inputs
from evaluation.commitloop.v5_reproduce import verify_seal
from evaluation.commitloop.v7_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    MASTER_SEED,
    SCHEMA_VERSION,
    VALID_CUTOFF,
    build_cohort,
    bundles_for_split,
    write_cohort,
)

PRIOR_REGISTRY_SCHEMA = "commitloop-prior-cohort-exclusions.v1"
KNOWN_REGISTRY_PATHS = (
    "evaluation/commitloop/prior_cohort_exclusion_registry.json",
    "artifacts/prior_cohort_exclusion_registry.json",
)
PROMPT_DIR = Path(__file__).parent / "prompts"
SCHEMA_DIR = Path(__file__).parent / "schemas"


class V7FreezeError(RuntimeError):
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


def _build_prior_registry(prior_runs: list[Path]) -> dict[str, Any]:
    """Derive the prior-cohort exclusion registry from sealed v5/v6 runs.

    Mirrors the ``v5_freeze._prior_registry`` pattern: every prior run must be
    seal-verified, then its observed subject tokens (``timeline.jsonl``) and
    bundle payload hashes (``source_manifest.json``) are collected.
    """

    if not prior_runs:
        raise V7FreezeError("v7_prior_cohort_registry_required")
    tokens: set[str] = set()
    bundle_hashes: set[str] = set()
    sources = []
    for run in prior_runs:
        verify_seal(run)
        timeline = [
            json.loads(line)
            for line in (run / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        source = json.loads((run / "source_manifest.json").read_text(encoding="utf-8"))
        run_tokens = {str(item["subject_token"]) for item in timeline}
        run_hashes = {str(item) for item in source.get("bundle_payload_sha256", [])}
        tokens.update(run_tokens)
        bundle_hashes.update(run_hashes)
        sources.append(
            {
                "run_name": run.name,
                "sealed_checksum_sha256": _sha256(run / "checksums.sha256"),
                "subject_count": len(run_tokens),
                "bundle_count": len(run_hashes),
            }
        )
    return {
        "schema_version": PRIOR_REGISTRY_SCHEMA,
        "sources": sources,
        "subject_tokens": sorted(tokens),
        "bundle_payload_sha256": sorted(bundle_hashes),
    }


def _load_prior_registry(
    *,
    repository_root: Path,
    prior_registry_path: Path | None,
    prior_runs: list[Path],
) -> dict[str, Any]:
    root = repository_root.resolve()
    if prior_registry_path is not None and prior_registry_path.is_file():
        loaded = json.loads(prior_registry_path.read_text(encoding="utf-8"))
        if loaded.get("schema_version") != PRIOR_REGISTRY_SCHEMA:
            raise V7FreezeError("v7_prior_registry_schema_invalid")
        return loaded
    for relative in KNOWN_REGISTRY_PATHS:
        candidate = root / relative
        if candidate.is_file():
            loaded = json.loads(candidate.read_text(encoding="utf-8"))
            if loaded.get("schema_version") != PRIOR_REGISTRY_SCHEMA:
                raise V7FreezeError("v7_prior_registry_schema_invalid")
            return loaded
    if prior_runs:
        return _build_prior_registry(prior_runs)
    raise V7FreezeError(
        "v7_prior_cohort_registry_required:"
        " pass --prior-registry or at least one sealed --prior-run"
        " (no prior_cohort_exclusion_registry.json exists under"
        " evaluation/commitloop/ or artifacts/)"
    )


def _prompt_and_schema_hashes() -> tuple[dict[str, str], dict[str, str]]:
    prompt_files = sorted(path for path in PROMPT_DIR.glob("*") if path.is_file())
    schema_files = sorted(path for path in SCHEMA_DIR.glob("*") if path.is_file())
    if not prompt_files or not schema_files:
        raise V7FreezeError("v7_prompt_or_schema_inventory_missing")
    return (
        {path.name: _sha256(path) for path in prompt_files},
        {path.name: _sha256(path) for path in schema_files},
    )


def create_v7_freeze(
    *,
    output_dir: Path,
    repository_root: Path,
    cohort_master_seed: int = MASTER_SEED,
    cohort_name: str = COHORT_NAME,
    cohort_schema_version: str = SCHEMA_VERSION,
    prior_registry_path: Path | None = None,
    prior_runs: list[Path] | None = None,
) -> Path:
    root, output_dir = repository_root.resolve(), output_dir.resolve()
    if output_dir.exists():
        raise V7FreezeError("v7_freeze_output_must_not_exist")
    if not _tracked_worktree_clean(root):
        raise V7FreezeError("v7_freeze_requires_clean_tracked_worktree")
    git_sha = _git(root, "rev-parse", "HEAD")
    output_dir.mkdir(parents=True)
    cohort_path, cohort_manifest_path = write_cohort(
        output_dir / "cohort",
        master_seed=cohort_master_seed,
        cohort_name=cohort_name,
        schema_version=cohort_schema_version,
    )
    rows, generated = build_cohort(
        master_seed=cohort_master_seed,
        cohort_name=cohort_name,
        schema_version=cohort_schema_version,
    )
    expected_split_counts = {
        "development": 192,
        "validation": 192,
        "sealed_test": 384,
    }
    if len(rows) != 768 or generated["split_counts"] != expected_split_counts:
        raise V7FreezeError("v7_cohort_inventory_invalid")
    case_counts = {
        split: expected_solver_case_count(
            bundles=bundles_for_split(rows, split=split)[0],
            valid_cutoff=VALID_CUTOFF,
            known_cutoff=KNOWN_CUTOFF,
            max_subjects=generated["split_counts"][split],
            max_base_cases=generated["split_counts"][split],
        )
        for split in ("development", "validation", "sealed_test")
    }
    if any(count < generated["split_counts"][split] for split, count in case_counts.items()):
        raise V7FreezeError("v7_adversarial_case_inventory_invalid")
    registry = _load_prior_registry(
        repository_root=root,
        prior_registry_path=prior_registry_path,
        prior_runs=list(prior_runs or []),
    )
    prior_tokens = set(registry["subject_tokens"])
    prior_hashes = set(registry["bundle_payload_sha256"])
    token_overlap = prior_tokens & {str(row["subject_token"]) for row in rows}
    hash_overlap = prior_hashes & {str(row["bundle_sha256"]) for row in rows}
    if token_overlap or hash_overlap:
        raise V7FreezeError("v7_prior_cohort_overlap_detected")
    registry_path = output_dir / "prior_cohort_exclusion_registry.json"
    registry_path.write_text(
        json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    prompt_hashes, schema_hashes = _prompt_and_schema_hashes()
    inputs = freeze_inputs(root)
    payload: dict[str, Any] = {
        "schema_version": "glhs-bench-v7-preprovider-freeze.v1",
        "status": "FROZEN_PRE_PROVIDER",
        "synthetic_software_evaluation_only": True,
        "clinical_adjudication": "NOT_RUN",
        "git_sha": git_sha,
        "provider_calls_before_freeze": 0,
        "cohort_sha256": _sha256(cohort_path),
        "cohort_manifest_sha256": _sha256(cohort_manifest_path),
        "cohort_spec": {
            "master_seed": cohort_master_seed,
            "cohort_name": cohort_name,
            "schema_version": cohort_schema_version,
        },
        "prior_registry_sha256": _sha256(registry_path),
        "prior_cohort_exclusion": {
            "subject_token_overlap": len(token_overlap),
            "bundle_hash_overlap": len(hash_overlap),
            "status": "PASS",
        },
        "input_sha256": {path: _sha256(root / path) for path in inputs},
        "prompt_sha256": prompt_hashes,
        "schema_sha256": schema_hashes,
        "execution_contract": {
            "models": list(CONFIRMATORY_MODELS),
            "primary_model": REVIEWER_MODEL,
            "reported_model_mapping": dict(REPORTED_MODEL_ID_BY_REQUESTED),
            "conditions": list(CONDITIONS),
            "max_concurrency": GLHS_BENCH_GLOBAL_CONCURRENCY,
            "batch_size": GLHS_BENCH_GLOBAL_CONCURRENCY,
            # Bounded retry budget for declared transient 429/5xx/timeout
            # failures. Terminal format/schema failures remain terminal.
            "max_retries": 5,
            "retry_scope": "declared_transient_429_5xx_timeout_only",
            "terminal_format_failures_terminal": True,
            "temperature": 0,
            "response_format": "json_object_with_frozen_local_schema_validation",
            "fallback": False,
            "development_subjects": 192,
            "validation_subjects": 192,
            "sealed_final_subjects": 384,
            "nominal_subject_level_solver_cells": 768 * len(CONDITIONS) * len(CONFIRMATORY_MODELS),
            "case_counts_including_all_adversarial_variants": case_counts,
            "solver_request_counts": {
                split: count * len(CONDITIONS) * len(CONFIRMATORY_MODELS)
                for split, count in case_counts.items()
            },
            "final_holdout_access": "PROHIBITED_UNTIL_FINAL_CANDIDATE_FREEZE",
        },
        "provider_probe_contract": {
            "schema_version": "glhs-bench-v7-provider-probe.v1",
            "requested_models": list(CONFIRMATORY_MODELS),
            "reported_model_mapping": dict(REPORTED_MODEL_ID_BY_REQUESTED),
            "fallback": False,
            "temperature": 0,
        },
        "statistics_plan": {
            "schema_version": "commitloop-primary-statistics.v1",
            "primary_unit": "subject",
            "primary_model": REVIEWER_MODEL,
            "reference_condition": "glhs_hybrid_thss_strict",
            "comparator_condition": "full_authorized_history",
            "endpoint": "all_axes_exact_match",
            "method": "paired_subject_exact_two_sided_sign_test_with_bootstrap_ci_95",
            "bootstrap_samples": 10000,
            "seed": 20260812,
            "primary_multiplicity": "none_one_primary_contrast",
            "status": "DESCRIPTIVE_SYNTHETIC_ONLY",
            "clinical_adjudication": "NOT_RUN",
        },
    }
    freeze_path = output_dir / "freeze.json"
    freeze_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return freeze_path


def verify_v7_freeze(*, freeze_path: Path, repository_root: Path) -> dict[str, Any]:
    payload = json.loads(freeze_path.read_text(encoding="utf-8"))
    root = repository_root.resolve()
    if payload.get("schema_version") != "glhs-bench-v7-preprovider-freeze.v1":
        raise V7FreezeError("v7_freeze_schema_invalid")
    if (
        payload.get("status") != "FROZEN_PRE_PROVIDER"
        or payload.get("provider_calls_before_freeze") != 0
    ):
        raise V7FreezeError("v7_freeze_provider_contract_invalid")
    if not _tracked_worktree_clean(root) or _git(root, "rev-parse", "HEAD") != payload.get(
        "git_sha"
    ):
        raise V7FreezeError("v7_freeze_git_drift")
    inputs = freeze_inputs(root)
    hashes = payload.get("input_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(inputs):
        raise V7FreezeError("v7_freeze_input_inventory_invalid")
    if any(hashes[path] != _sha256(root / path) for path in inputs):
        raise V7FreezeError("v7_freeze_input_drift")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--prior-registry", type=Path, default=None)
    parser.add_argument("--prior-run", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        freeze_path = create_v7_freeze(
            output_dir=args.output,
            repository_root=args.repo_root,
            prior_registry_path=args.prior_registry,
            prior_runs=args.prior_run,
        )
    except (V7FreezeError, ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.error(str(exc))
    print(freeze_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
