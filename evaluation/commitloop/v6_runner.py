"""Run one preassigned non-final v6 partition through the GLHS-Bench path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.commitloop.production_context import (
    compile_production_commitment_context,
)
from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REPORTED_MODEL_ID_BY_REQUESTED,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_local import expected_solver_case_count, run_local_e2e
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v6_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    VALID_CUTOFF,
    bundles_for_split,
)
from evaluation.commitloop.v6_freeze import verify_v6_freeze


def run_v6_development_partition(
    *,
    rows: list[dict[str, Any]],
    split: str,
    output_dir: Path,
    cohort_name: str = COHORT_NAME,
    clients: dict[str, EvaluationClient],
    freeze_path: Path,
    provider_probe_path: Path,
    repository_root: Path,
    limits: RunLimits,
) -> dict[str, Any]:
    """Run only development/validation; sealed final has a separate gate."""

    if split not in {"development", "validation"}:
        raise ValueError("v6_nonfinal_split_required")
    unverified_bundles, _unverified_splits = bundles_for_split(rows, split=split)
    if (
        limits.max_subjects != len(unverified_bundles)
        or limits.max_cases != len(unverified_bundles)
    ):
        raise ValueError("v6_partition_limits_must_match_split")
    freeze = verify_v6_freeze(freeze_path=freeze_path, repository_root=repository_root)
    frozen_cohort_path = freeze_path.parent / "cohort" / "cohort.jsonl"
    frozen_manifest_path = freeze_path.parent / "cohort" / "cohort_manifest.json"
    if (
        not frozen_cohort_path.is_file()
        or not frozen_manifest_path.is_file()
        or hashlib.sha256(frozen_cohort_path.read_bytes()).hexdigest()
        != freeze.get("cohort_sha256")
        or hashlib.sha256(frozen_manifest_path.read_bytes()).hexdigest()
        != freeze.get("cohort_manifest_sha256")
    ):
        raise ValueError("v6_frozen_cohort_artifact_integrity_invalid")
    frozen_rows = [
        json.loads(line)
        for line in frozen_cohort_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if rows != frozen_rows:
        raise ValueError("v6_cohort_rows_drift_from_freeze")
    bundles, splits = bundles_for_split(frozen_rows, split=split)
    expected_cases = expected_solver_case_count(
        bundles=bundles,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        max_subjects=limits.max_subjects,
        max_base_cases=limits.max_cases,
    )
    expected_requests = expected_cases * len(CONDITIONS) * len(clients)
    if limits.max_requests < expected_requests:
        raise ValueError("v6_partition_request_budget_insufficient")
    execution_contract = freeze.get("execution_contract")
    if (
        not isinstance(execution_contract, dict)
        or execution_contract
        .get("case_counts_including_all_adversarial_variants", {})
        .get(split)
        != expected_cases
        or execution_contract.get("solver_request_counts", {}).get(split)
        != expected_requests
    ):
        raise ValueError("v6_frozen_case_inventory_contract_invalid")
    probe = json.loads(provider_probe_path.read_text(encoding="utf-8"))
    probe_hash = hashlib.sha256(provider_probe_path.read_bytes()).hexdigest()
    if (
        probe.get("schema_version") != "glhs-bench-v6-provider-probe.v1"
        or probe.get("git_sha") != freeze["git_sha"]
        or probe.get("freeze_sha256")
        != hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        or probe.get("requested_models") != list(CONFIRMATORY_MODELS)
        or probe.get("reported_model_mapping") != REPORTED_MODEL_ID_BY_REQUESTED
        or probe.get("fallback") is not False
        or len(probe.get("results", [])) != len(CONFIRMATORY_MODELS)
    ):
        raise ValueError("v6_provider_probe_contract_invalid")
    return run_local_e2e(
        bundles=bundles,
        output_dir=output_dir,
        clients=clients,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        limits=limits,
        execution_mode="glhs_bench_router",
        phase_a_freeze_sha=str(freeze["git_sha"]),
        provider_probe_sha256=probe_hash,
        source_cohort=f"{cohort_name}:{split}",
        primary_model="claude-sonnet-4.6",
        production_strict_context_builder=compile_production_commitment_context,
        subject_splits=splits,
        include_all_adversarial_variants=True,
    )
