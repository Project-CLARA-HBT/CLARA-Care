"""Probe and record the exact two-model v6 router contract."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.commitloop.provider import (
    CONFIRMATORY_MODELS,
    REPORTED_MODEL_ID_BY_REQUESTED,
    EvaluationClient,
    parse_json_object_content,
)
from evaluation.commitloop.v6_freeze import verify_v6_freeze

PROBE_SCHEMA = {
    "name": "glhs_bench_v6_probe",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {"status": {"const": "ok"}},
    },
    "strict": True,
}


def probe_v6_models(
    *,
    freeze_path: Path,
    output_path: Path,
    clients: dict[str, EvaluationClient],
    repository_root: Path,
) -> dict[str, Any]:
    freeze = verify_v6_freeze(freeze_path=freeze_path, repository_root=repository_root)
    if set(clients) != set(CONFIRMATORY_MODELS):
        raise ValueError("v6_probe_exact_models_required")
    results = []
    for model in CONFIRMATORY_MODELS:
        result = clients[model].complete(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a JSON API. Output exactly one JSON object and no prose.",
                },
                {
                    "role": "user",
                    "content": 'Output exactly this object: {"status":"ok"}',
                },
            ],
            response_schema=PROBE_SCHEMA,
            max_tokens=64,
        )
        if parse_json_object_content(result.content) != {"status": "ok"}:
            raise ValueError("v6_probe_response_invalid")
        results.append(
            {
                "requested_model_id": result.requested_model_id,
                "reported_model_id": result.reported_model_id,
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
                "usage": result.usage,
                "latency_ms": result.latency_ms,
                "attempts": result.attempts,
                "base_url_sha256": clients[model].base_url_sha256,
            }
        )
    payload = {
        "schema_version": "glhs-bench-v6-provider-probe.v1",
        "freeze_sha256": hashlib.sha256(freeze_path.read_bytes()).hexdigest(),
        "git_sha": freeze["git_sha"],
        "requested_models": list(CONFIRMATORY_MODELS),
        "reported_model_mapping": REPORTED_MODEL_ID_BY_REQUESTED,
        "fallback": False,
        "temperature": 0,
        "results": results,
        "recorded_at_utc": datetime.now(UTC).isoformat(),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload
