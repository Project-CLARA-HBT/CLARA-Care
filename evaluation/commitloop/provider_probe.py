"""Phase-B exact-model probe; guarded by a sealed Phase-A implementation freeze."""

from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.freeze import verify_live_repository_matches_freeze
from evaluation.commitloop.http_transport import UrllibJsonTransport
from evaluation.commitloop.provider import (
    GENERATOR_MODEL,
    REPORTED_MODEL_ID_BY_REQUESTED,
    REVIEWER_MODEL,
    EvaluationClient,
    RunLimits,
)
from evaluation.commitloop.validate import validate_run

PROBE_SCHEMA = {
    "name": "commitloop_probe_v1",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {"status": {"const": "ok"}},
    },
    "strict": True,
}


def _freeze(path: Path, *, repository_root: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if path.name != "implementation_freeze.json":
        raise ValueError("implementation_freeze_filename_required")
    if (
        payload.get("phase_a_status") != "COMPLETE"
        or payload.get("router_calls_before_freeze") != 0
        or payload.get("router_calls_before_initial_freeze", 0) != 0
        or not isinstance(payload.get("git_sha"), str)
        or not payload["git_sha"]
    ):
        raise ValueError("phase_a_freeze_required")
    validate_run(path.parent)
    verify_live_repository_matches_freeze(payload, repository_root)
    return payload


def run_probe(
    *,
    freeze_path: Path,
    output: Path,
    clients: dict[str, EvaluationClient],
    repository_root: Path = Path("."),
) -> dict[str, Any]:
    freeze = _freeze(freeze_path, repository_root=repository_root)
    sealed_root = freeze_path.resolve().parent
    resolved_output = output.resolve()
    if resolved_output == sealed_root or sealed_root in resolved_output.parents:
        raise ValueError("probe_output_must_not_modify_phase_a_seal")
    expected = {GENERATOR_MODEL, REVIEWER_MODEL}
    if set(clients) != expected:
        raise ValueError("exact_two_model_probe_required")
    results = []
    for model in sorted(clients):
        result = clients[model].complete(
            model=model,
            messages=[{"role": "user", "content": "Return the probe JSON only."}],
            response_schema=PROBE_SCHEMA,
            max_tokens=64,
        )
        parsed = json.loads(result.content)
        if parsed != {"status": "ok"}:
            raise ValueError("probe_schema_or_content_invalid")
        results.append(
            {
                "requested_model_id": result.requested_model_id,
                "reported_model_id": result.reported_model_id,
                "model_family": (
                    "gemini"
                    if result.requested_model_id == GENERATOR_MODEL
                    else "claude"
                ),
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
                "usage": result.usage,
                "token_usage_available": bool(result.usage),
                "token_usage_fields": sorted(result.usage),
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "retries": max(0, result.attempts - 1),
                "response_schema_name": PROBE_SCHEMA["name"],
                "json_contract_supported": True,
                "stream_requested": False,
                "streaming_behavior": "non_streaming_response",
                "base_url_sha256": clients[model].base_url_sha256,
            }
        )
    payload = {
        "schema_version": "commitloop-provider-probe.v2",
        "phase_a_freeze_sha": freeze["git_sha"],
        "requested_models": sorted(clients),
        "exact_model_policy": "reported_must_match_declared_mapping",
        "reported_model_mapping": REPORTED_MODEL_ID_BY_REQUESTED,
        "fallback_allowed": False,
        "request_parameters": {
            "temperature": 0,
            "max_tokens": 64,
            "stream": False,
        },
        "results": results,
        "recorded_at": datetime.now(UTC).isoformat(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    key = os.environ.get("ROUTER_API_KEY", "")
    base_url = os.environ.get("ROUTER_BASE_URL", "")
    limits = RunLimits.from_env()
    clients = {
        model: EvaluationClient(
            base_url=base_url,
            api_key=key,
            transport=UrllibJsonTransport(),
            limits=limits,
        )
        for model in (GENERATOR_MODEL, REVIEWER_MODEL)
    }
    result = run_probe(
        freeze_path=args.freeze,
        output=args.output,
        clients=clients,
        repository_root=args.repo_root,
    )
    print(
        json.dumps({"models": result["requested_models"], "status": "probe_complete"})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
