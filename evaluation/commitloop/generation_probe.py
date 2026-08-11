"""Bounded Phase-B smoke test for source-grounded construction stages."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.candidate_mining import mine_candidates
from evaluation.commitloop.fhir_ingest import ingest_bundle
from evaluation.commitloop.fixtures import controlled_benchmark_bundles
from evaluation.commitloop.generation import construct_with_model_review
from evaluation.commitloop.http_transport import UrllibJsonTransport
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REVIEWER_MODEL,
    EvaluationClient,
    ProviderError,
    RunLimits,
)
from evaluation.commitloop.run_benchmark import _phase_b_preflight


def run_generation_probe(
    *,
    freeze_path: Path,
    probe_path: Path,
    output: Path,
    clients: dict[str, EvaluationClient],
    repository_root: Path = Path("."),
) -> dict[str, Any]:
    freeze_sha, probe_sha = _phase_b_preflight(
        freeze_path=freeze_path,
        probe_path=probe_path,
        repository_root=repository_root,
    )
    if set(clients) != {GENERATOR_MODEL, REVIEWER_MODEL}:
        raise ValueError("generation_probe_exact_two_models_required")
    sealed_root = freeze_path.resolve().parent
    resolved_output = output.resolve()
    if resolved_output == sealed_root or sealed_root in resolved_output.parents:
        raise ValueError("generation_probe_must_not_modify_phase_a_seal")
    if resolved_output == probe_path.resolve():
        raise ValueError("generation_probe_must_not_overwrite_provider_probe")
    cutoff = datetime(2026, 2, 1, tzinfo=UTC)
    subject_token, events = ingest_bundle(
        controlled_benchmark_bundles()[0],
        fhir_version="R4",
        ingested_at=cutoff,
    )
    case = mine_candidates(subject_token, events)[0]
    before = sum(client.request_count for client in clients.values())
    attempts_before = sum(client.attempt_count for client in clients.values())
    try:
        result = construct_with_model_review(
            case=case,
            events=events,
            generator=clients[GENERATOR_MODEL],
            reviewer=clients[REVIEWER_MODEL],
        )
        status = "ACCEPTED"
        error_type = None
    except (
        ProviderError,
        json.JSONDecodeError,
        OSError,
        TimeoutError,
        TypeError,
        ValueError,
    ) as exc:
        result = None
        status = "REJECTED"
        error_type = type(exc).__name__
    request_count = sum(client.request_count for client in clients.values()) - before
    attempt_count = (
        sum(client.attempt_count for client in clients.values()) - attempts_before
    )
    result_summary = None
    if result is not None:
        stages = result.get("stages")
        if not isinstance(stages, list):
            raise TypeError("generation_probe_stages_invalid")
        result_summary = {
            "status": result.get("status"),
            "validator_decision": result.get("validator_decision"),
            "stage_count": len(stages),
            "stage_records": stages,
            "result_sha256": hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    payload = {
        "schema_version": "commitloop-generation-probe.v1",
        "phase_a_freeze_sha": freeze_sha,
        "provider_probe_sha256": probe_sha,
        "source_cohort": "controlled_r4_mechanism_cohort.v1",
        "case_id_sha256": hashlib.sha256(case.case_id.encode()).hexdigest(),
        "requested_models": sorted(clients),
        "status": status,
        "error_type": error_type,
        "request_count": request_count,
        "max_request_count": 2,
        "attempt_count": attempt_count,
        "max_attempt_count": 2,
        "result_summary": result_summary,
        "clinical_adjudication": "NOT_RUN",
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    if request_count > 2 or attempt_count > 2:
        raise ValueError("generation_probe_request_budget_exceeded")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--probe", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    limits = replace(RunLimits.from_env(), max_retries=0)
    clients = {
        model: EvaluationClient(
            base_url=os.environ.get("ROUTER_BASE_URL", ""),
            api_key=os.environ.get("ROUTER_API_KEY", ""),
            transport=UrllibJsonTransport(),
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }
    result = run_generation_probe(
        freeze_path=args.freeze,
        probe_path=args.probe,
        output=args.output,
        clients=clients,
        repository_root=args.repo_root,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "requests": result["request_count"],
            },
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "ACCEPTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
