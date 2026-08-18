"""Run one preassigned non-final v7 partition through the GLHS-Bench path."""

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
from evaluation.commitloop.run_local import (
    expected_solver_case_count,
    run_local_e2e,
    seal_artifacts,
)
from evaluation.commitloop.solver_packets import CONDITIONS
from evaluation.commitloop.v7_cohort import (
    COHORT_NAME,
    KNOWN_CUTOFF,
    VALID_CUTOFF,
    bundles_for_split,
)
from evaluation.commitloop.v7_freeze import verify_v7_freeze


def sanitize_artifact_cohort(value: Any) -> tuple[Any, int]:
    """Redact synthetic FHIR subject references from a sealed public artifact.

    The frozen source cohort is retained outside the run artifact and is verified
    before execution.  The copy placed alongside a run is evidence for split
    membership and construction provenance, not an executable FHIR payload, so
    it must not retain subject-reference strings.
    """

    if isinstance(value, dict):
        redacted = 0
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "reference" and isinstance(item, str) and item.lower().startswith("patient/"):
                result[key] = "urn:glhs-bench:redacted-subject"
                redacted += 1
            else:
                sanitized, count = sanitize_artifact_cohort(item)
                result[key] = sanitized
                redacted += count
        return result, redacted
    if isinstance(value, list):
        redacted = 0
        result: list[Any] = []
        for item in value:
            sanitized, count = sanitize_artifact_cohort(item)
            result.append(sanitized)
            redacted += count
        return result, redacted
    return value, 0


def run_v7_development_partition(
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
        raise ValueError("v7_nonfinal_split_required")
    unverified_bundles, _unverified_splits = bundles_for_split(rows, split=split)
    if (
        limits.max_subjects != len(unverified_bundles)
        or limits.max_cases != len(unverified_bundles)
    ):
        raise ValueError("v7_partition_limits_must_match_split")
    freeze = verify_v7_freeze(freeze_path=freeze_path, repository_root=repository_root)
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
        raise ValueError("v7_frozen_cohort_artifact_integrity_invalid")
    frozen_rows = [
        json.loads(line)
        for line in frozen_cohort_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if rows != frozen_rows:
        raise ValueError("v7_cohort_rows_drift_from_freeze")
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
        raise ValueError("v7_partition_request_budget_insufficient")
    execution_contract = freeze.get("execution_contract")
    if (
        not isinstance(execution_contract, dict)
        or limits.max_concurrency != execution_contract.get("max_concurrency")
        or limits.max_retries != execution_contract.get("max_retries")
        or execution_contract
        .get("case_counts_including_all_adversarial_variants", {})
        .get(split)
        != expected_cases
        or execution_contract.get("solver_request_counts", {}).get(split)
        != expected_requests
    ):
        raise ValueError("v7_frozen_case_inventory_contract_invalid")
    probe = json.loads(provider_probe_path.read_text(encoding="utf-8"))
    probe_hash = hashlib.sha256(provider_probe_path.read_bytes()).hexdigest()
    if (
        probe.get("schema_version") != "glhs-bench-v7-provider-probe.v1"
        or probe.get("git_sha") != freeze["git_sha"]
        or probe.get("freeze_sha256")
        != hashlib.sha256(freeze_path.read_bytes()).hexdigest()
        or probe.get("requested_models") != list(CONFIRMATORY_MODELS)
        or probe.get("reported_model_mapping") != REPORTED_MODEL_ID_BY_REQUESTED
        or probe.get("fallback") is not False
        or len(probe.get("results", [])) != len(CONFIRMATORY_MODELS)
    ):
        raise ValueError("v7_provider_probe_contract_invalid")
    result = run_local_e2e(
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
    # A non-final run must be reproducible from its own sealed directory while
    # never copying the withheld cohort rows into a development/validation
    # artifact. The original pre-provider freeze remains immutable elsewhere.
    artifact_inputs = output_dir / "frozen_inputs"
    artifact_inputs.mkdir(exist_ok=False)
    selected_rows = [
        row for row in frozen_rows if str(row.get("split")) == split
    ]
    selected_cohort = artifact_inputs / f"cohort_{split}.jsonl"
    sanitized_rows: list[dict[str, Any]] = []
    subject_reference_redactions = 0
    for row in selected_rows:
        sanitized, count = sanitize_artifact_cohort(row)
        if not isinstance(sanitized, dict):  # pragma: no cover - cohort rows are dicts by contract
            raise TypeError("v7_sanitized_cohort_row_invalid")
        sanitized_rows.append(sanitized)
        subject_reference_redactions += count
    selected_cohort.write_text(
        "".join(
            json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n"
            for row in sanitized_rows
        ),
        encoding="utf-8",
    )
    copied_freeze = artifact_inputs / "freeze.json"
    copied_probe = artifact_inputs / "provider_probe.json"
    copied_freeze.write_bytes(freeze_path.read_bytes())
    copied_probe.write_bytes(provider_probe_path.read_bytes())
    provenance = {
        "schema_version": "glhs-bench-v7-run-inputs.v1",
        "split": split,
        "freeze_sha256": hashlib.sha256(copied_freeze.read_bytes()).hexdigest(),
        "provider_probe_sha256": hashlib.sha256(copied_probe.read_bytes()).hexdigest(),
        "full_cohort_sha256": hashlib.sha256(frozen_cohort_path.read_bytes()).hexdigest(),
        "selected_cohort_sha256": hashlib.sha256(selected_cohort.read_bytes()).hexdigest(),
        "implementation_git_sha": str(freeze["git_sha"]),
        "redaction": {
            "algorithm": "fhir_subject_reference_v1",
            "subject_reference_redactions": subject_reference_redactions,
        },
    }
    (artifact_inputs / "artifact_provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    seal_artifacts(output_dir)
    return result
