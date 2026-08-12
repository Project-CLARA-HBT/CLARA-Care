"""Run one preassigned non-final v6 partition through the GLHS-Bench path."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.commitloop.production_context import (
    compile_production_commitment_context,
)
from evaluation.commitloop.provider import EvaluationClient, RunLimits
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v6_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    VALID_CUTOFF,
    bundles_for_split,
)


def run_v6_development_partition(
    *,
    rows: list[dict[str, Any]],
    split: str,
    output_dir: Path,
    clients: dict[str, EvaluationClient],
    phase_freeze_sha: str,
    provider_probe_sha256: str,
    limits: RunLimits,
) -> dict[str, Any]:
    """Run only development/validation; sealed final has a separate gate."""

    if split not in {"development", "validation"}:
        raise ValueError("v6_nonfinal_split_required")
    bundles, splits = bundles_for_split(rows, split=split)
    expected_requests = len(bundles) * len(CONDITIONS) * len(clients)
    if limits.max_subjects != len(bundles) or limits.max_cases != len(bundles):
        raise ValueError("v6_partition_limits_must_match_split")
    if limits.max_requests < expected_requests:
        raise ValueError("v6_partition_request_budget_insufficient")
    return run_local_e2e(
        bundles=bundles,
        output_dir=output_dir,
        clients=clients,
        valid_cutoff=VALID_CUTOFF,
        known_cutoff=KNOWN_CUTOFF,
        limits=limits,
        execution_mode="glhs_bench_router",
        phase_a_freeze_sha=phase_freeze_sha,
        provider_probe_sha256=provider_probe_sha256,
        source_cohort=f"{COHORT_NAME}:{split}",
        primary_model="claude-sonnet-4.6",
        production_strict_context_builder=compile_production_commitment_context,
        subject_splits=splits,
    )
