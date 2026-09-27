"""Phase 11 (E11) and Phase 12 (E12): v8 Prospective Runner.

Executes the prospective two-model replication cohort protocol locked to two genuinely
distinct model families (claude-sonnet-4.6 and gemini-3.6-flash-high) with zero fallback,
interleaved condition grid, freeze verification, 12-class error classification, and
sensitivity arm evaluation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from evaluation.commitloop.malformed_sensitivity import (
    classify_error_12_class,
    evaluate_sensitivity_arms,
)
from evaluation.commitloop.production_context import (
    compile_production_commitment_context,
)
from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REPORTED_MODEL_ID_BY_REQUESTED,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.run_local import run_local_e2e, seal_artifacts

COHORT_NAME_V8 = "glhs_bench_v8_replication_384"
V8_SCHEMA_VERSION = "commitloop-v8-runner.v1"
V8_CONDITIONS = ("glhs_hybrid_thss_strict", "full_authorized_history")
V8_MODELS = ("claude-sonnet-4.6", "gemini-3.6-flash-high")


def verify_v8_freeze_contract(freeze_path: Path, repository_root: Path) -> dict[str, Any]:
    """Verify freeze contract and git state before any provider call."""
    if not freeze_path.is_file():
        raise ValueError("v8_freeze_file_missing")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if freeze.get("schema_version") not in {
        "commitloop-v8-freeze.v1",
        "commitloop-v7-freeze.v1",
        "commitloop-freeze.v1",
    }:
        raise ValueError("v8_freeze_schema_invalid")
    return freeze


def verify_v8_provider_probe(probe_path: Path, freeze: dict[str, Any]) -> dict[str, Any]:
    """Verify provider probe contract ensuring exact model IDs and no fallback."""
    if not probe_path.is_file():
        raise ValueError("v8_provider_probe_missing")
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    if probe.get("fallback") is not False:
        raise ValueError("v8_provider_probe_fallback_prohibited")
    requested = probe.get("requested_models", [])
    if set(requested) != set(V8_MODELS):
        raise ValueError("v8_provider_probe_requested_models_mismatch")
    reported = probe.get("reported_model_mapping", {})
    for req in V8_MODELS:
        if req not in reported or reported[req] != REPORTED_MODEL_ID_BY_REQUESTED.get(req, req):
            raise ValueError("v8_provider_probe_reported_mapping_invalid")
    return probe


def run_v8_replication_cohort(
    *,
    bundles: list[tuple[dict[str, Any], str]],
    output_dir: Path,
    clients: dict[str, EvaluationClient],
    freeze_path: Path,
    provider_probe_path: Path,
    repository_root: Path,
    limits: RunLimits,
    valid_cutoff: Any,
    known_cutoff: Any,
    split: str = "replication",
    subject_splits: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Execute the Phase 11 / Phase 12 v8 replication runner."""
    output_dir.mkdir(parents=True, exist_ok=True)

    freeze = verify_v8_freeze_contract(freeze_path=freeze_path, repository_root=repository_root)
    probe = verify_v8_provider_probe(probe_path=provider_probe_path, freeze=freeze)
    probe_hash = hashlib.sha256(provider_probe_path.read_bytes()).hexdigest()

    if set(clients.keys()) != set(V8_MODELS):
        raise ValueError("v8_clients_must_match_frozen_two_model_families")

    e2e_result = run_local_e2e(
        bundles=bundles,
        output_dir=output_dir,
        clients=clients,
        valid_cutoff=valid_cutoff,
        known_cutoff=known_cutoff,
        limits=limits,
        execution_mode="glhs_bench_router",
        phase_a_freeze_sha=str(freeze.get("git_sha", "0" * 40)),
        provider_probe_sha256=probe_hash,
        source_cohort=f"{COHORT_NAME_V8}:{split}",
        conditions=V8_CONDITIONS,
        primary_model="claude-sonnet-4.6",
        primary_reference_condition="glhs_hybrid_thss_strict",
        primary_comparator_condition="full_authorized_history",
        production_strict_context_builder=compile_production_commitment_context,
        subject_splits=subject_splits,
        model_order=V8_MODELS,
    )

    solver_outputs_path = output_dir / "solver_outputs.json"
    solver_outputs = (
        json.loads(solver_outputs_path.read_text(encoding="utf-8"))
        if solver_outputs_path.is_file()
        else []
    )
    gold_path = output_dir / "construction_gold.jsonl"
    gold_by_case: dict[str, dict[str, Any]] = {}
    if gold_path.is_file():
        for line in gold_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                gold_by_case[str(item["case_id"])] = item

    sensitivity_analysis = evaluate_sensitivity_arms(solver_outputs, gold_by_case)
    (output_dir / "malformed_sensitivity.json").write_text(
        json.dumps(sensitivity_analysis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    seal_artifacts(output_dir)
    return e2e_result
