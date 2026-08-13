"""Fail-closed validation for local or provider-backed CommitLoop artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    reported_model_matches_requested,
)
from evaluation.commitloop.run_local import (
    _PREDICTION_SCHEMA_SHA256,
    _SOLVER_PROMPT_SHA256,
    _validate_solver_prediction,
)
from evaluation.commitloop.solver_packets import CONDITIONS

REQUIRED = frozenset(
    {
        "run_manifest.json",
        "source_manifest.json",
        "model_manifest.json",
        "protocol_manifest.json",
        "partition_manifest.json",
        "timeline.jsonl",
        "commitments.jsonl",
        "synthetic_notes.jsonl",
        "perturbation_manifest.jsonl",
        "construction_gold.jsonl",
        "model_generation.json",
        "model_generation.jsonl",
        "generation_error_ledger.json",
        "solver_outputs.json",
        "error_ledger.json",
        "error_ledger.csv",
        "metrics.json",
        "per_case_metrics.csv",
        "statistical_results.json",
        "validation_report.json",
        "report.md",
        "checkpoint.json",
        "checksums.sha256",
    }
)


def validate_run(root: Path) -> None:
    missing = [name for name in REQUIRED if not (root / name).is_file()]
    if missing:
        raise ValueError("missing_run_artifacts:" + ",".join(sorted(missing)))
    checksums = (root / "checksums.sha256").read_text(encoding="utf-8").splitlines()
    if not checksums:
        raise ValueError("empty_artifact_seal")
    sealed_paths = set()
    for line in checksums:
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise ValueError("malformed_artifact_checksum") from exc
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("malformed_artifact_checksum")
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative in sealed_paths
        ):
            raise ValueError("unsafe_artifact_checksum_path")
        sealed_paths.add(relative)
        path = root / relative_path
        if (
            not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            raise ValueError("artifact_checksum_mismatch")
    actual_paths = {
        str(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    }
    if sealed_paths != actual_paths:
        raise ValueError("artifact_seal_inventory_mismatch")
    manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
    perturbations = [
        json.loads(line)
        for line in (root / "perturbation_manifest.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line
    ]
    outputs = json.loads((root / "solver_outputs.json").read_text(encoding="utf-8"))
    errors = json.loads((root / "error_ledger.json").read_text(encoding="utf-8"))
    if not isinstance(outputs, list) or not isinstance(errors, list):
        raise TypeError("invalid_run_ledger")
    keys = [item.get("key") for item in [*outputs, *errors] if isinstance(item, dict)]
    if len(keys) != len(set(keys)) or any(not isinstance(key, str) for key in keys):
        raise ValueError("duplicate_or_invalid_run_key")
    if manifest.get("solver_request_count") != len(keys):
        raise ValueError("run_request_count_mismatch")
    generation = json.loads(
        (root / "model_generation.json").read_text(encoding="utf-8")
    )
    generation_errors = json.loads(
        (root / "generation_error_ledger.json").read_text(encoding="utf-8")
    )
    if not isinstance(generation, list) or not isinstance(generation_errors, list):
        raise TypeError("invalid_generation_ledger")
    generation_requests = sum(
        len(item.get("stages", [])) for item in generation if isinstance(item, dict)
    ) + sum(
        int(item.get("request_count", 0))
        for item in generation_errors
        if isinstance(item, dict)
    )
    if manifest.get("generation_request_count") != generation_requests:
        raise ValueError("generation_request_count_mismatch")
    expected_models = sorted((GENERATOR_MODEL, REVIEWER_MODEL))
    for item in generation:
        if not isinstance(item, dict) or not isinstance(item.get("stages"), list):
            raise TypeError("invalid_generation_record")
        if "gold" in json.dumps(item, sort_keys=True).lower():
            raise ValueError("generation_gold_leakage_detected")
        for stage in item["stages"]:
            if not isinstance(stage, dict):
                raise TypeError("invalid_generation_stage")
            if not reported_model_matches_requested(
                str(stage.get("requested_model_id")), stage.get("reported_model_id")
            ):
                raise ValueError("model_substitution_detected")
            if stage.get("requested_model_id") not in expected_models:
                raise ValueError("unexpected_model_id")
    statistics = json.loads(
        (root / "statistical_results.json").read_text(encoding="utf-8")
    )
    if (
        not isinstance(statistics, dict)
        or statistics.get("clinical_adjudication") != "NOT_RUN"
    ):
        raise ValueError("invalid_statistical_results")
    if manifest.get("request_count") != len(keys) + generation_requests:
        raise ValueError("run_request_count_mismatch")
    if manifest.get("completed_cell_count") != len(keys):
        raise ValueError("run_checkpoint_count_mismatch")
    if manifest.get("conditions") != list(CONDITIONS):
        raise ValueError("run_conditions_mismatch")
    if manifest.get("models") != expected_models:
        raise ValueError("run_models_mismatch")
    protocol_manifest = json.loads(
        (root / "protocol_manifest.json").read_text(encoding="utf-8")
    )
    if not isinstance(protocol_manifest, dict):
        raise TypeError("protocol_manifest_invalid")
    protocol_payload = {
        key: value
        for key, value in protocol_manifest.items()
        if key != "protocol_sha256"
    }
    protocol_hash = hashlib.sha256(
        json.dumps(
            protocol_payload, sort_keys=True, separators=(",", ":"), default=str
        ).encode()
    ).hexdigest()
    if (
        protocol_payload.get("schema_version") != "commitloop-protocol.v2"
        or protocol_payload.get("solver_contract") != "commitloop-solver.v5"
        or protocol_payload.get("timeliness_oracle")
        != "decisive_event_else_cutoff_with_domain_default_grace"
        or protocol_manifest.get("protocol_sha256") != protocol_hash
    ):
        raise ValueError("protocol_manifest_invalid")
    model_manifest = json.loads(
        (root / "model_manifest.json").read_text(encoding="utf-8")
    )
    if (
        not isinstance(model_manifest, dict)
        or model_manifest.get("reported_model_policy")
        != "must_match_declared_mapping"
        or model_manifest.get("reported_model_mapping")
        != REPORTED_MODEL_ID_BY_REQUESTED
        or model_manifest.get("fallback") is not False
    ):
        raise ValueError("model_manifest_mapping_invalid")
    execution_mode = manifest.get("execution_mode", "phase_a_fake")
    if execution_mode not in {
        "phase_a_fake",
        "phase_b_router",
        "glhs_bench_router",
    }:
        raise ValueError("invalid_execution_mode")
    if execution_mode in {"phase_b_router", "glhs_bench_router"}:
        if not re.fullmatch(
            r"(?:[0-9a-f]{40}|[0-9a-f]{64})",
            str(manifest.get("phase_a_freeze_sha") or ""),
        ):
            raise ValueError("phase_b_provenance_missing:phase_a_freeze_sha")
        if not re.fullmatch(
            r"[0-9a-f]{64}", str(manifest.get("provider_probe_sha256") or "")
        ):
            raise ValueError("phase_b_provenance_missing:provider_probe_sha256")
    if execution_mode == "glhs_bench_router" and str(manifest.get("source_cohort", "")).startswith(
        "glhs_bench_"
    ):
        inputs = root / "frozen_inputs"
        required_inputs = {
            "freeze.json",
            "provider_probe.json",
            "artifact_provenance.json",
            f"cohort_{str(manifest.get('source_cohort', '')).rsplit(':', 1)[-1]}.jsonl",
        }
        if not inputs.is_dir() or any(not (inputs / name).is_file() for name in required_inputs):
            raise ValueError("glhs_bench_frozen_input_artifact_missing")
        provenance = json.loads((inputs / "artifact_provenance.json").read_text(encoding="utf-8"))
        split = str(manifest.get("source_cohort", "")).rsplit(":", 1)[-1]
        selected_cohort = inputs / f"cohort_{split}.jsonl"
        if (
            not isinstance(provenance, dict)
            or provenance.get("schema_version") != "glhs-bench-v6-run-inputs.v2"
            or provenance.get("split") != split
            or provenance.get("freeze_sha256")
            != hashlib.sha256((inputs / "freeze.json").read_bytes()).hexdigest()
            or provenance.get("provider_probe_sha256")
            != hashlib.sha256((inputs / "provider_probe.json").read_bytes()).hexdigest()
            or provenance.get("selected_cohort_sha256")
            != hashlib.sha256(selected_cohort.read_bytes()).hexdigest()
            or not isinstance(provenance.get("redaction"), dict)
            or provenance["redaction"].get("algorithm")
            != "fhir_subject_reference_v1"
            or not isinstance(provenance["redaction"].get("subject_reference_redactions"), int)
            or provenance["redaction"]["subject_reference_redactions"] < 1
        ):
            raise ValueError("glhs_bench_frozen_input_artifact_invalid")
        selected_rows = [
            json.loads(line)
            for line in selected_cohort.read_text(encoding="utf-8").splitlines()
            if line
        ]
        partitions = json.loads((root / "partition_manifest.json").read_text(encoding="utf-8"))
        selected_tokens = {str(row.get("subject_token")) for row in selected_rows}
        if (
            not isinstance(partitions, dict)
            or not selected_rows
            or any(str(row.get("split")) != split for row in selected_rows)
            or selected_tokens != {
                str(subject)
                for subject, assigned in partitions.items()
                if assigned == split
            }
        ):
            raise ValueError("glhs_bench_frozen_input_subject_inventory_invalid")
    expected_cells = manifest.get("expected_cell_count")
    if not isinstance(expected_cells, int) or expected_cells < 0:
        raise ValueError("invalid_expected_cell_count")
    if manifest.get("run_status") == "COMPLETE" and len(keys) != expected_cells:
        raise ValueError("incomplete_complete_run")
    metrics = json.loads((root / "metrics.json").read_text(encoding="utf-8"))
    if not isinstance(metrics, dict) or not isinstance(metrics.get("axes"), dict):
        raise TypeError("invalid_metrics_artifact")
    if set(metrics["axes"]) != {
        "lifecycle_state",
        "evidence_state",
        "timeliness_state",
    }:
        raise ValueError("metrics_axes_mismatch")
    for axis_metrics in metrics["axes"].values():
        if (
            not isinstance(axis_metrics, dict)
            or axis_metrics.get("denominator") != expected_cells
        ):
            raise ValueError("metrics_axis_denominator_mismatch")
    exact_metrics = metrics.get("all_axes_exact_match")
    if (
        not isinstance(exact_metrics, dict)
        or exact_metrics.get("denominator") != expected_cells
    ):
        raise ValueError("metrics_exact_denominator_mismatch")
    escalation_metrics = metrics.get("escalation_accuracy")
    if (
        not isinstance(escalation_metrics, dict)
        or escalation_metrics.get("denominator") != expected_cells
    ):
        raise ValueError("metrics_escalation_denominator_mismatch")
    generation_metrics = metrics.get("generation")
    if not isinstance(generation_metrics, dict) or generation_metrics.get(
        "expected_case_count"
    ) != manifest.get("source_case_count", manifest.get("case_count")):
        raise ValueError("generation_metrics_case_count_mismatch")
    if generation_metrics.get("mode") == "deterministic_construction_only":
        if generation_metrics.get("model_review_request_count") != 0:
            raise ValueError("deterministic_generation_request_count_invalid")
    else:
        candidate_slots = generation_metrics.get("candidate_slot")
        if not isinstance(candidate_slots, dict) or candidate_slots.get(
            "denominator"
        ) != (manifest.get("source_case_count", manifest.get("case_count", 0)) * 4):
            raise ValueError("generation_metrics_candidate_denominator_mismatch")
    variant_metrics = metrics.get("adversarial_variants")
    if not isinstance(variant_metrics, dict) or variant_metrics.get(
        "variant_case_count"
    ) != manifest.get("variant_case_count", 0):
        raise ValueError("variant_metrics_case_count_mismatch")
    variant_escalation = variant_metrics.get("escalation_accuracy")
    if not isinstance(variant_escalation, dict) or variant_escalation.get(
        "denominator"
    ) != manifest.get("variant_case_count", 0) * len(expected_models) * len(CONDITIONS):
        raise ValueError("variant_escalation_denominator_mismatch")
    transition_metrics = variant_metrics.get("transition_sequence_accuracy")
    expected_boundary_pairs = sum(
        item.get("variant_kind")
        in {"late_ingestion", "post_cutoff_evidence"}
        for item in perturbations
        if isinstance(item, dict)
    ) * len(expected_models) * len(CONDITIONS)
    if not isinstance(transition_metrics, dict) or transition_metrics.get(
        "denominator"
    ) != expected_boundary_pairs:
        raise ValueError("transition_sequence_denominator_mismatch")
    boundary_metrics = variant_metrics.get("valid_known_time_boundary_accuracy")
    if not isinstance(boundary_metrics, dict):
        raise TypeError("boundary_metrics_missing")
    for boundary, variant_kind in (
        ("known_time", "late_ingestion"),
        ("valid_time", "post_cutoff_evidence"),
    ):
        expected = sum(
            item.get("variant_kind") == variant_kind
            for item in perturbations
            if isinstance(item, dict)
        ) * len(expected_models) * len(CONDITIONS)
        item = boundary_metrics.get(boundary)
        if not isinstance(item, dict) or item.get("denominator") != expected:
            raise ValueError("boundary_metrics_denominator_mismatch")
    solver_cell_keys: dict[Path, set[str]] = {}
    for output in outputs:
        _validate_solver_prediction(output.get("prediction"))
        if not reported_model_matches_requested(
            str(output.get("requested_model_id")), output.get("reported_model_id")
        ):
            raise ValueError("model_substitution_detected")
        if output.get("requested_model_id") not in expected_models:
            raise ValueError("unexpected_model_id")
        if output.get("condition") not in CONDITIONS:
            raise ValueError("unexpected_condition")
        if output.get("prompt_sha256") != _SOLVER_PROMPT_SHA256:
            raise ValueError("solver_prompt_hash_mismatch")
        if output.get("schema_sha256") != _PREDICTION_SCHEMA_SHA256:
            raise ValueError("prediction_schema_hash_mismatch")
        output_path = (
            Path("solver_outputs")
            / str(output["requested_model_id"]).replace("/", "__")
            / f"{output['condition']}.jsonl"
        )
        absolute_output_path = root / output_path
        if not absolute_output_path.is_file():
            raise ValueError("missing_solver_cell_artifact")
        cell_keys = solver_cell_keys.get(output_path)
        if cell_keys is None:
            cell_keys = {
                str(json.loads(line)["key"])
                for line in absolute_output_path.read_text(encoding="utf-8").splitlines()
                if line
            }
            solver_cell_keys[output_path] = cell_keys
        if str(output["key"]) not in cell_keys:
            raise ValueError("solver_cell_artifact_mismatch")
    for condition in CONDITIONS:
        if not (root / "solver_packets" / f"{condition}.jsonl").is_file():
            raise ValueError("missing_solver_packet_artifact")
    # "authorization" is a legitimate THSS pipeline stage.  Scan for an
    # actual credential-header pattern instead of rejecting that safety term.
    forbidden = (
        b"authorization: bearer ",
        b"bearer ",
        b"router_api_key",
        b"patient/",
    )
    for path in root.rglob("*"):
        if path.is_file() and path.name != "checksums.sha256":
            lowered = path.read_bytes().lower()
            if any(marker in lowered for marker in forbidden):
                raise ValueError("secret_or_header_material_in_artifact")
