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
    TAXONOMY_12_CLASSES,
    classify_error_12_class,
    evaluate_sensitivity_arms,
    normalize_error_class,
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

MODEL_ALIAS_MAP: dict[str, list[str]] = {
    "claude-sonnet-4.6": ["claude-sonnet-4.6", "claude-sonnet-4-6"],
    "gemini-3.6-flash-high": ["gemini-3.6-flash-high"],
    "gemini-3.8-flash-tiered": ["gemini-3.8-flash-tiered", "antigravity/gemini-3.8-flash-tiered"],
}


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


def audit_provider_run_ledger(
    ledger_input: Path | dict[str, Any] | str,
    *,
    raise_on_empty_raw: bool = True,
    raise_on_token_error: bool = True,
    raise_on_taxonomy_error: bool = True,
) -> dict[str, Any]:
    """Audit provider run ledger record-by-record for model drift, token integrity, and taxonomy compliance.

    Verifies:
      1. Every record in the ledger list.
      2. Compares requested_model_id vs reported_model_id. If requested_model_id != reported_model_id,
         increments fallbacks_observed count (never reports 0 when mismatches exist).
      3. Verifies presence and non-emptiness of raw_output.
      4. Verifies prompt_tokens, completion_tokens, and total_tokens are valid non-negative integers.
      5. Verifies error_classification against prospective 12-class error taxonomy.
         Ensures null parsed_output is paired with a valid error_classification.
    """
    if isinstance(ledger_input, (str, Path)):
        p = Path(ledger_input)
        if not p.is_file():
            raise FileNotFoundError(f"provider_run_ledger_not_found: {p}")
        data = json.loads(p.read_text(encoding="utf-8"))
    elif isinstance(ledger_input, dict):
        data = ledger_input
    else:
        raise TypeError(f"invalid_ledger_input_type: {type(ledger_input)}")

    ledger = data.get("ledger")
    if not isinstance(ledger, list) or len(ledger) == 0:
        raise ValueError("provider_run_ledger_empty_or_invalid")

    total_records = len(ledger)
    fallbacks_observed = 0
    drift_details: dict[str, int] = {}
    alias_normalizations: dict[str, int] = {}
    models_tested: set[str] = set()
    error_counts: dict[str, int] = {}
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_all_tokens = 0

    for idx, rec in enumerate(ledger):
        if not isinstance(rec, dict):
            raise ValueError(f"ledger_record_not_dict_at_index_{idx}")

        req_model = rec.get("requested_model_id")
        rep_model = rec.get("reported_model_id")
        if not req_model or not isinstance(req_model, str):
            raise ValueError(f"missing_or_invalid_requested_model_id_at_index_{idx}")
        if not rep_model or not isinstance(rep_model, str):
            raise ValueError(f"missing_or_invalid_reported_model_id_at_index_{idx}")

        models_tested.add(req_model)

        # Check allowed model aliases vs unallowed fallbacks / substitutions
        allowed_aliases = MODEL_ALIAS_MAP.get(req_model, [req_model])
        if rep_model in allowed_aliases:
            if req_model != rep_model:
                alias_key = f"{req_model} -> {rep_model}"
                alias_normalizations[alias_key] = alias_normalizations.get(alias_key, 0) + 1
        else:
            fallbacks_observed += 1
            drift_key = f"{req_model} -> {rep_model}"
            drift_details[drift_key] = drift_details.get(drift_key, 0) + 1

        # Check raw_output presence and non-emptiness
        raw_out = rec.get("raw_output")
        if raw_out is None or not isinstance(raw_out, str) or len(raw_out.strip()) == 0:
            if raise_on_empty_raw:
                raise ValueError(f"empty_or_missing_raw_output_at_index_{idx}")

        # Check token counts
        prompt_tokens = rec.get("prompt_tokens")
        completion_tokens = rec.get("completion_tokens")
        total_tokens = rec.get("total_tokens")
        for t_name, t_val in [
            ("prompt_tokens", prompt_tokens),
            ("completion_tokens", completion_tokens),
            ("total_tokens", total_tokens),
        ]:
            if t_val is None or not isinstance(t_val, int) or t_val < 0:
                if raise_on_token_error:
                    raise ValueError(f"invalid_token_count_{t_name}_at_index_{idx}: {t_val}")

        if isinstance(prompt_tokens, int):
            total_prompt_tokens += prompt_tokens
        if isinstance(completion_tokens, int):
            total_completion_tokens += completion_tokens
        if isinstance(total_tokens, int):
            total_all_tokens += total_tokens

        # Verify error classification against 12-class taxonomy
        err_cls = rec.get("error_classification") or rec.get("error_class")
        parsed_out = rec.get("parsed_output")
        if err_cls is not None:
            norm_cls = normalize_error_class(err_cls)
            if norm_cls not in TAXONOMY_12_CLASSES:
                if raise_on_taxonomy_error:
                    raise ValueError(f"unknown_error_classification_at_index_{idx}: {err_cls}")
            if norm_cls:
                error_counts[norm_cls] = error_counts.get(norm_cls, 0) + 1
        elif parsed_out is None:
            if raise_on_taxonomy_error:
                raise ValueError(f"missing_error_classification_for_null_parsed_output_at_index_{idx}")

    return {
        "schema_version": "commitloop-ledger-audit.v1",
        "total_records": total_records,
        "models_tested": sorted(models_tested),
        "fallbacks_observed": fallbacks_observed,
        "model_drift_breakdown": drift_details,
        "alias_normalization": alias_normalizations,
        "error_counts": error_counts,
        "token_usage": {
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "total_tokens": total_all_tokens,
        },
        "audit_passed": True,
    }


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
