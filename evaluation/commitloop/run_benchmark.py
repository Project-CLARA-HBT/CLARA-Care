"""Freeze-gated, bounded Phase-B CommitLoop synthetic benchmark runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.fixtures import controlled_benchmark_bundles
from evaluation.commitloop.http_transport import UrllibJsonTransport
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.provider_probe import _freeze
from evaluation.commitloop.run_local import run_local_e2e
from evaluation.commitloop.validate import validate_run

_EXACT_MODELS = frozenset({GENERATOR_MODEL, REVIEWER_MODEL})
_FHIR_VERSIONS = frozenset({"R4", "STU3"})
_MAX_BUNDLE_BYTES = 50 * 1024 * 1024


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_cutoff(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid_benchmark_cutoff") from exc
    if parsed.tzinfo is None:
        raise ValueError("timezone_aware_benchmark_cutoff_required")
    return parsed


def _validate_probe(path: Path, *, freeze_sha: str) -> str:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "commitloop-provider-probe.v2":
        raise ValueError("phase_b_probe_schema_invalid")
    if payload.get("phase_a_freeze_sha") != freeze_sha:
        raise ValueError("phase_b_probe_freeze_mismatch")
    if set(payload.get("requested_models") or []) != _EXACT_MODELS:
        raise ValueError("phase_b_probe_models_invalid")
    if (
        payload.get("exact_model_policy") != "reported_must_match_declared_mapping"
        or payload.get("reported_model_mapping") != REPORTED_MODEL_ID_BY_REQUESTED
        or payload.get("fallback_allowed") is not False
    ):
        raise ValueError("phase_b_probe_model_policy_invalid")
    results = payload.get("results")
    if not isinstance(results, list) or len(results) != len(_EXACT_MODELS):
        raise ValueError("phase_b_probe_results_invalid")
    seen = set()
    for item in results:
        if not isinstance(item, dict):
            raise TypeError("phase_b_probe_results_invalid")
        requested = item.get("requested_model_id")
        if (
            requested not in _EXACT_MODELS
            or item.get("reported_model_id") != REPORTED_MODEL_ID_BY_REQUESTED[requested]
            or item.get("json_contract_supported") is not True
            or item.get("stream_requested") is not False
            or item.get("streaming_behavior") != "non_streaming_response"
            or not re.fullmatch(r"[0-9a-f]{64}", str(item.get("base_url_sha256") or ""))
        ):
            raise ValueError("phase_b_probe_capability_invalid")
        seen.add(requested)
    if seen != _EXACT_MODELS:
        raise ValueError("phase_b_probe_models_invalid")
    return _sha256(path)


def _load_bundles(
    paths: list[Path], *, fhir_version: str, limits: RunLimits
) -> list[tuple[dict[str, Any], str]]:
    if fhir_version not in _FHIR_VERSIONS:
        raise ValueError("unsupported_fhir_version")
    if not paths or len(paths) > limits.max_subjects:
        raise ValueError("bundle_count_outside_run_limit")
    bundles = []
    for path in paths:
        if not path.is_file() or path.stat().st_size > _MAX_BUNDLE_BYTES:
            raise ValueError("invalid_or_oversized_bundle")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TypeError("fhir_bundle_must_be_object")
        bundles.append((payload, fhir_version))
    return bundles


def _bounded_bundle_directory(path: Path, *, max_subjects: int) -> list[Path]:
    if not path.is_dir():
        raise ValueError("bundle_directory_required")
    selected = []
    for item in path.iterdir():
        if item.is_file() and item.suffix.lower() == ".json":
            selected.append(item)
            if len(selected) > max_subjects:
                raise ValueError("bundle_count_outside_run_limit")
    return sorted(selected)


def _phase_b_preflight(
    *, freeze_path: Path, probe_path: Path, repository_root: Path
) -> tuple[str, str]:
    freeze = _freeze(freeze_path, repository_root=repository_root)
    freeze_sha = str(freeze["git_sha"])
    return freeze_sha, _validate_probe(probe_path, freeze_sha=freeze_sha)


def run_phase_b_benchmark(
    *,
    freeze_path: Path,
    probe_path: Path,
    output_dir: Path,
    bundles: list[tuple[dict[str, Any], str]],
    clients: dict[str, EvaluationClient],
    valid_cutoff: datetime,
    known_cutoff: datetime,
    limits: RunLimits,
    repository_root: Path = Path("."),
    source_cohort: str = "injected_fhir_bundles",
) -> dict[str, Any]:
    freeze_sha, probe_sha = _phase_b_preflight(
        freeze_path=freeze_path,
        probe_path=probe_path,
        repository_root=repository_root,
    )
    sealed_root = freeze_path.resolve().parent
    resolved_output = output_dir.resolve()
    if resolved_output == sealed_root or sealed_root in resolved_output.parents:
        raise ValueError("phase_b_output_must_not_modify_phase_a_seal")
    if set(clients) != _EXACT_MODELS:
        raise ValueError("phase_b_exact_two_models_required")
    if not bundles or len(bundles) > limits.max_subjects:
        raise ValueError("bundle_count_outside_run_limit")
    if valid_cutoff.tzinfo is None or known_cutoff.tzinfo is None:
        raise ValueError("timezone_aware_benchmark_cutoff_required")
    manifest = run_local_e2e(
        bundles=bundles,
        output_dir=output_dir,
        clients=clients,
        construction_clients=(clients[GENERATOR_MODEL], clients[REVIEWER_MODEL]),
        valid_cutoff=valid_cutoff,
        known_cutoff=known_cutoff,
        limits=limits,
        execution_mode="phase_b_router",
        phase_a_freeze_sha=freeze_sha,
        provider_probe_sha256=probe_sha,
        source_cohort=source_cohort,
    )
    validate_run(output_dir)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    bundle_source = parser.add_mutually_exclusive_group(required=True)
    bundle_source.add_argument("--bundle", type=Path, action="append")
    bundle_source.add_argument("--bundle-dir", type=Path)
    bundle_source.add_argument("--controlled-fixture-cohort", action="store_true")
    parser.add_argument("--fhir-version", choices=sorted(_FHIR_VERSIONS))
    parser.add_argument("--valid-cutoff", required=True)
    parser.add_argument("--known-cutoff", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()

    # Verify the Phase-A seal and exact-model probe before reading credentials or
    # constructing a transport capable of network I/O.
    _phase_b_preflight(
        freeze_path=args.freeze,
        probe_path=args.probe,
        repository_root=args.repo_root,
    )
    limits = RunLimits.from_env()
    if args.controlled_fixture_cohort:
        if args.fhir_version is not None:
            parser.error("--fhir-version is not used with --controlled-fixture-cohort")
        bundles = [(bundle, "R4") for bundle in controlled_benchmark_bundles()]
        source_cohort = "controlled_r4_mechanism_cohort.v1"
    else:
        if args.fhir_version is None:
            parser.error("--fhir-version is required with --bundle or --bundle-dir")
        bundle_paths = (
            list(args.bundle)
            if args.bundle
            else _bounded_bundle_directory(
                args.bundle_dir,
                max_subjects=limits.max_subjects,
            )
        )
        bundles = _load_bundles(bundle_paths, fhir_version=args.fhir_version, limits=limits)
        source_cohort = "injected_fhir_bundles"
    base_url = os.environ.get("ROUTER_BASE_URL", "")
    api_key = os.environ.get("ROUTER_API_KEY", "")
    clients = {
        model: EvaluationClient(
            base_url=base_url,
            api_key=api_key,
            transport=UrllibJsonTransport(),
            limits=limits,
        )
        for model in sorted(_EXACT_MODELS)
    }
    manifest = run_phase_b_benchmark(
        freeze_path=args.freeze,
        probe_path=args.probe,
        output_dir=args.output,
        bundles=bundles,
        clients=clients,
        valid_cutoff=_parse_cutoff(args.valid_cutoff),
        known_cutoff=_parse_cutoff(args.known_cutoff),
        limits=limits,
        repository_root=args.repo_root,
        source_cohort=source_cohort,
    )
    print(
        json.dumps(
            {
                "status": manifest["run_status"],
                "subjects": manifest["subject_count"],
                "cases": manifest["case_count"],
                "requests": manifest["request_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
